# ליבת ה-Saga: החוזה שהאבנים נבנות לפיו

**סטטוס:** הוחלט (S1–S3)
**תאריך:** 2026-10-27
**מבוסס על:** `saga.md` (סעיפים 2, 3, 8, 9, 10, 12), והמחקר בסוף המסמך.

המסמך מגדיר את החוזה בין המנוע לצעדים, ברמה שאפשר לכתוב לפיה קוד. `saga.md` מתאר מה כל צעד עושה מול
הקלאסטר, והמסמך הזה מתאר איך הצעדים והמנוע מתחברים.

---

## 1. עקרונות (מהמחקר ומ-`saga.md`)

| עיקרון | מקור | מה זה אומר אצלנו |
|---|---|---|
| תזמור מרכזי (orchestration) | Microsoft, Richardson | מנוע אחד מריץ את הצעדים. הצעדים לא מכירים זה את זה |
| המצב נשמר לפני כל פעולה | Microsoft | saga record נכתב לפני כל צעד, וגם מיד כשיש תוצאה |
| סדר: הפיכים, pivot, ניתנים לחזרה | Garcia-Molina | כבר ב-`saga.md`, והמנוע בודק אותו |
| פיצוי idempotent, ולא עושה כלום כשאין מה לבטל | כל המקורות | 404 בביטול = כבר בוטל |
| timeout הוא לא כישלון | כל המקורות | תוצאה לא ידועה מבררים לפני ניסיון חוזר (`find_outcome`) |
| רק המנוע מחזיק מצב | `saga.md` סעיף 2 | צעד בלי מצב. הקלט והתוצאה נשמרים ב-context |

## 2. החוזה של צעד

```python
class StepKind(StrEnum):
    COMPENSATABLE = "compensatable"
    PIVOT = "pivot"
    RETRIABLE = "retriable"


class SagaStep[TInput: BaseModel, TResult: BaseModel](Protocol):
    @property
    def kind(self) -> StepKind: ...

    def execute(self, *, step_input: TInput, keep_result: KeepResult[TResult]) -> None: ...

    def find_outcome(self, *, step_input: TInput) -> TResult | None: ...

    def compensate(self, *, step_input: TInput, result: TResult) -> None: ...
```

- **התלויות** (repository, waiter) בקונסטרקטור. **הנתונים** (קלאסטר יעד, spec) ב-`step_input`. כך הצעד בלי מצב.
- **`step_input` ו-`result` הם מודלי Pydantic,** כדי שאפשר יהיה לשמור אותם ב-saga record ולקרוא אותם בחזרה.
- **`keep_result`** נקרא ברגע שהתוצאה ידועה, לפני ההמתנה. צעד שיש לו תוצאה מבוטל גם אם לא הגיע ל-`done`.
- **`find_outcome`** עונה על "האם הפעולה כבר בוצעה?" אחרי תוצאה לא ידועה, ומחזיר את התוצאה אם כן.
- **`compensate`** idempotent. אם אין מה לבטל, הוא לא עושה כלום.

### מה כל צעד שבנינו או שנבנה מממש

| צעד | `step_input` | `result` | `find_outcome` | `compensate` |
|---|---|---|---|---|
| יצירת user / role / ACL | target + spec | `CreatedResource` | `find_by_name(spec.name)` | `delete`, ‏404 = כבר בוטל |
| יצירת DB | target + spec | `CreatedResource` | `find_by_name` (שם לא ייחודי: יותר מאחד ⇐ התערבות ידנית, 5.4) | `delete`, המתנה ל-404 |
| עדכון DB / הרשאות | target + uid + values | snapshot | האם הערכים הנוכחיים שווים לחדשים | `PUT` של ה-snapshot |
| יצירת CRDB | target + spec + `X-Task-ID` | guid | `GET /v1/crdb_tasks/{X-Task-ID}` | `DELETE` + task |
| עדכון CRDB / הרשאות AA | target + guid + values | snapshot | השוואה | `PATCH` של ה-snapshot |
| מחיקת user | target + uid + snapshot + password | - | האם היוזר עדיין קיים | **pivot**, אין פיצוי |

## 3. קלט שתלוי בצעד קודם

ל-role צריך את ה-uid של ה-DB, ולמשתמש את ה-uid של ה-role. התוכנית בונה את הקלט של כל צעד **כשמגיע תורו**,
מתוך ה-context:

```python
class PlannedStep[TInput, TResult](BaseModel):
    key: str                                    # ייחודי בתוכנית: "cluster1/role/db1-app-role/create"
    step: SagaStep[TInput, TResult]
    build_input: Callable[[SagaContext], TInput]
```

- **ה-context** הוא מיפוי מ-`key` לתוצאה של הצעד (`CreatedResource`, snapshot). הוא חלק מה-saga record.
- **הצעד לא קורא מה-context.** רק התוכנית יודעת איזה צעד צריך תוצאה של איזה צעד. הצעד מקבל קלט מוכן ומוקלד.
- **AA:** אותו צעד מופיע פעם לכל קלאסטר, עם `key` שמתחיל בקלאסטר.

## 4. המנוע

לכל צעד, לפי הסדר:

1. **בונים קלט** מה-context, ושומרים ב-record: `running` + הקלט.
2. **`execute`**. כש-`keep_result` נקרא, התוצאה נשמרת ב-context וב-record מיד.
3. **הצליח:** `done`.
4. **נכשל:** לפי סוג השגיאה (`saga.md` סעיף 8):

| שגיאה | המנוע עושה |
|---|---|
| `ClusterRequestError` זמני (`409 busy`, `wrong_cluster_state_id`, מהקונפיג) | ניסיון חוזר לפי מדיניות |
| `ClusterRequestError` אחר | הצעד נכשל ⇐ פיצוי |
| `InvalidEdgeRequestError` | הצעד נכשל ⇐ פיצוי (באג אצלנו) |
| כל שגיאת קצה אחרת, timeout של המתנה | `find_outcome`: נמצא ⇐ `done`. לא נמצא ⇐ ניסיון חוזר. גם הבדיקה נכשלה ⇐ ממתינים ומנסים שוב |
| נגמרו הניסיונות | הצעד נכשל ⇐ פיצוי |

5. **פיצוי:** כל צעד **שיש לו תוצאה** ב-context, בסדר הפוך, עם ניסיונות חוזרים. נכשל ⇐ `compensation_failed`,
   וה-Saga מסומן `requires_manual_intervention` (סעיף 9).
6. **אחרי pivot:** אין פיצוי. כשל בצעד שניתן לחזרה ⇐ ניסיונות חוזרים, ואז התערבות ידנית.
7. **נעילה:** המנוע לוקח את נעילת ה-DB לפני הצעד הראשון ומשחרר בסוף, כולל אחרי פיצוי (סעיף 10).
8. **קריסה:** לפי D5. בעלייה לא ממשיכים ולא מבטלים, רק מסמנים להתערבות ידנית.

## 5. Saga record

| שדה | תוכן |
|---|---|
| `saga_id` | ה-trace ID של הבקשה |
| `status` | `running`, `succeeded`, `rolled_back`, `requires_manual_intervention` |
| `steps[]` | `key`, `kind`, `status`, `step_input`, `result`, `error` |

- **שלב 1:** `SagaStateRepository` בזיכרון. **לפני production:** Redis (הוחלט).
- **סודות לא נכנסים ל-record:** הסיסמה של `default_user` ופרטי הגישה לקלאסטרים לא חלק מ-`step_input`. הצעד
  מקבל אותם מהקונפיג או מה-registry בזמן הריצה. סיסמאות של יוזרי DB כן נכנסות (5.3).

## 6. ספרייה או מימוש שלנו

**מה ספרייה נותנת:** בעיקר המשך אוטומטי אחרי קריסה (durable execution). אצלנו הוחלט שאחרי קריסה **לא ממשיכים
ולא מבטלים** (D5), ולכן החלק הכי קשה שספריות פותרות לא נדרש.

| אפשרות | Redis | כמה pods | מה זה דורש | מתאים? |
|---|---|---|---|---|
| Temporal | לא (Cassandra / Postgres / MySQL) | כן | שרת Temporal, workflow דטרמיניסטי | כבד, ובלי Redis |
| **Dapr Workflow** | **כן** (state store) | **כן** | Dapr מותקן על ה-OpenShift (control plane + sidecar לכל pod), workflow דטרמיניסטי | **החלופה הרצינית**, אם Dapr כבר קיים בארגון |
| sagaz | רק כ-cache. האחסון הוא Postgres | - | async בלבד | לא מתאים: sync ו-Redis |
| sagakit | כן | לא ברור | ספרייה קטנה, בלי repo ציבורי שמצאתי | לא בשל מספיק |
| Restate, Hatchet, DBOS | לא | כן | שרת נוסף או Postgres | תשתית נוספת |
| **מימוש שלנו** | כן | כן, ראו למטה | המנוע מסעיף 4 | **ההמלצה** |

**כמה pods במימוש שלנו:** Saga רץ כולו ב-pod שקיבל את הבקשה, ב-worker ברקע. ה-saga record והנעילה של ה-DB
ב-Redis (`SET NX` עם TTL), כך ש:
- שני pods לא ירוצו על אותו DB (סעיף 10).
- כל pod יכול לענות ל-`GET /v1/operations/{trace_id}`, כי ה-record ב-Redis.
- pod שקרס משאיר Saga ב-`running` שהנעילה שלו פגה. pod אחר מזהה אותו בעלייה או בבדיקה תקופתית, ומסמן
  `requires_manual_intervention` (D5).

## 7. ניסיונות חוזרים (הוחלט)

שתי מדיניות, מהקונפיג: אחת לצעדים (שגיאה זמנית, ולא נמצא אחרי תוצאה לא ידועה), ואחת לפיצויים. לכל אחת מספר
ניסיונות ו-backoff. השגיאות שנחשבות זמניות (`busy`, `wrong_cluster_state_id`) גם הן בקונפיג.

## 8. החלטות

| # | נושא | החלטה |
|---|---|---|
| S1 | קלט שתלוי בצעד קודם | התוכנית בונה את הקלט מה-context (`build_input`, סעיף 3). הצעד לא מכיר את ה-context |
| S2 | ספרייה או מימוש שלנו | מימוש שלנו (סעיף 6). אין Dapr או תשתית אחרת ב-OpenShift, וההמשך אחרי קריסה לא נדרש (D5) |
| S3 | ניסיונות חוזרים | שתי מדיניות מהקונפיג, לצעדים ולפיצויים (סעיף 7) |

## מקורות

- [Saga pattern, Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Richardson, Managing data consistency using sagas (slides)](https://backiee.wasmer.app/https_www_slideshare_net/slideshow/microcph-managing-data-consistency-in-a-microservice-architecture-using-sagas/146951030)
- [Saga timeouts: the compensation path most teams never test](https://dev.to/gabrielanhaia/saga-timeouts-the-compensation-path-most-teams-never-test-1dok)
- [Compensations need idempotency keys too](https://codemia.io/archive/saga-pattern-for-distributed-transactions)
- [Saga orchestration pattern (2026)](https://appscale.blog/en/blog/microservices-pattern-saga-orchestration-2026)
- [Durable workflow engines comparison](https://dev.to/mahdi0shamlou/mahdi-shamlou-durable-workflow-engines-comparison-temporal-dbos-transact-prefect-custom-3a6a)
