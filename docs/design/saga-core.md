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

    def find_outcome(self, *, step_input: TInput, kept: TResult | None) -> TResult | None: ...

    def compensate(self, *, step_input: TInput, result: TResult) -> None: ...
```

- **התלויות** (repository, waiter, ספק פרטי הגישה) בקונסטרקטור. **הנתונים** ב-`step_input`. כך הצעד בלי מצב.
- **`step_input` מחזיק רק כתובת של קלאסטר** (`ClusterAddress`: רשת ו-URL), בלי פרטי גישה. הצעד מקבל את פרטי הגישה
  בזמן הריצה מ-`ClusterCredentialsProvider`, ולכן הם לא מגיעים ל-saga record. עד שיהיה registry של קלאסטרים,
  `SharedCredentialsProvider` נותן את אותם פרטי admin לכל קלאסטר.
- **`step_input` ו-`result` הם מודלי Pydantic,** כדי שאפשר יהיה לשמור אותם ב-saga record ולקרוא אותם בחזרה.
  המנוע מחזיק את האובייקט בזיכרון ומעביר אותו ל-`find_outcome` ול-`compensate`. ל-saga record נכתב עותק (`model_dump`),
  רק לתיעוד ולשאילתת הסטטוס: אחרי קריסה לא ממשיכים ולא מבטלים (D5), ולכן אין צורך לבנות תוצאה מחדש מה-record.
- **`keep_result`** נקרא ברגע שהתוצאה ידועה, לפני ההמתנה. צעד שיש לו תוצאה מבוטל גם אם לא הגיע ל-`done`.
- **`find_outcome`** עונה על "האם הפעולה כבר בוצעה?" אחרי תוצאה לא ידועה, ומחזיר את התוצאה אם כן. הוא מקבל את
  מה שהמנוע כבר שמר (`kept`): בעדכון ה-snapshot נשמר לפני ה-`PUT`, ואי אפשר לבנות אותו מחדש מהקלאסטר.
- **`compensate`** idempotent. אם אין מה לבטל, הוא לא עושה כלום.

### מה כל צעד שבנינו או שנבנה מממש

`find_by_name` מחזיר רשימה. ב-user, role ו-ACL הקלאסטר אוכף שם ייחודי, ולכן יש לכל היותר אחד. ב-DB השם לא
ייחודי (V2), ואם נמצא יותר מאחד, `find_outcome` זורק `AmbiguousResourceError`.

| צעד | `step_input` | `result` | `find_outcome` | `compensate` |
|---|---|---|---|---|
| יצירת user / role / ACL | כתובת קלאסטר + spec | `CreatedResource` | `find_by_name(spec.name)`, בלי `action_uid` | `delete`, ‏404 = כבר בוטל |
| יצירת DB | כתובת קלאסטר + spec (בלי הסיסמה של `default_user`) | `CreatedResource` | `find_by_name` (שם לא ייחודי: יותר מאחד ⇐ `AmbiguousResourceError`, התערבות ידנית, 5.4) | `delete`, המתנה ל-404 |
| עדכון DB / הרשאות | כתובת קלאסטר + uid + values | snapshot | הערכים הנוכחיים שווים לחדשים ⇐ ה-`kept` | `PUT` של ה-snapshot |
| יצירת CRDB (צעד משלו: מזהה guid, ממתין ל-task) | כתובת קלאסטר + spec + `X-Task-ID` | guid | `GET /v1/crdb_tasks/{X-Task-ID}` | `DELETE` + task |
| עדכון CRDB / הרשאות AA | כתובת קלאסטר + guid + values | snapshot | השוואה | `PATCH` של ה-snapshot |
| מחיקת user | כתובת קלאסטר + uid + snapshot + password | - | האם היוזר עדיין קיים | **pivot**, אין פיצוי |

## 3. קלט שתלוי בצעד קודם

ל-role צריך את ה-uid של ה-DB, ולמשתמש את ה-uid של ה-role. התוכנית בונה את הקלט של כל צעד **כשמגיע תורו**,
מתוך ה-context:

```python
class PlannedStep[TInput, TResult]:
    key: str  # ייחודי בתוכנית: "cluster1/role/db1-app-role/create"
    step: SagaStep[TInput, TResult]
    build_input: Callable[[SagaContext], TInput]
```

- **`PlannedStep` הוא מחלקה רגילה,** ולא מודל: הוא מחזיק צעד ופונקציה, ולא נתונים שנשמרים.
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
| `ClusterActionFailedError` (ה-action הסתיים ב-`failed`, `cancelled` או `aborted`) | הצעד נכשל ⇐ פיצוי. זו תוצאה ידועה, ולא מנסים שוב |
| `AmbiguousResourceError` מ-`find_outcome` (יותר ממשאב אחד באותו שם) | התערבות ידנית מיד: לא מנסים שוב ולא מפצים שום צעד, כי לא ידוע איזה משאב שלנו |
| כל שגיאה אחרת של הפרויקט (למשל `UnrestorableFieldsError`) | הצעד נכשל ⇐ פיצוי, בלי ניסיון חוזר: היא תחזור באותה צורה |
| שגיאה מתוך `find_outcome` | אותו מיון כמו בטבלה: `ClusterActionFailedError` ⇐ פיצוי, `AmbiguousResourceError` ⇐ התערבות ידנית, וכל השאר ⇐ ממתינים ומנסים את הבדיקה שוב, עד מדיניות הניסיונות של הצעדים. אם התוצאה עדיין לא ידועה ⇐ התערבות ידנית, כי ייתכן שהפעולה בוצעה |
| כל שגיאת קצה אחרת, timeout של המתנה, תשובה שלא נקראת (`UnreadableAnswerError`), או שגיאה זמנית אחרי שכבר יש תוצאה | `find_outcome`: נמצא ⇐ `done`. לא נמצא ⇐ ניסיון חוזר. גם הבדיקה נכשלה ⇐ ממתינים ומנסים שוב |
| נגמרו הניסיונות | הצעד נכשל ⇐ פיצוי. אם בדרך הייתה תוצאה לא ידועה ואין לצעד תוצאה שמורה ⇐ התערבות ידנית |

- **רק ה-`keep_result` הראשון של צעד נשמר.** אחרי תוצאה לא ידועה המנוע קורא קודם ל-`find_outcome`, ורק אם לא
  נמצא כלום הוא מריץ את `execute` שוב. כך ניסיון חוזר לא מחליף את ה-snapshot הראשון.
- **`find_outcome` מחזיר תוצאה רק אחרי ההמתנה של הצעד.** אם יש `kept` (ה-`POST` ענה), הוא סומך עליו ולא מחפש
  לפי שם. אחרת הוא מחפש לפי שם. בשני המקרים הוא מחכה לסיום (`wait_created`) לפני שהוא מחזיר, כדי שה-Saga לא ידווח
  הצלחה בזמן שה-DB עוד `pending`, ושהביטול לא ירוץ במקביל לפעולה שעוד רצה. משאב שנמצא לפי שם בלי `action_uid`
  (user, role, ACL) לא נמתן, כי ה-action שלו לא ידוע. אם הוא עוד רץ, הצעד הבא יקבל `busy`, עם ניסיון חוזר.
- **ה-record שומר איך התוצאה הושגה:** מ-`keep_result` או מחיפוש לפי שם. בביטול של משאב שנמצא לפי שם נרשם WARNING,
  כי הבדיקה המוקדמת לא מכסה את הזמן שבינה לבין ה-`POST`. ייבנה עם המנוע.
- **`find_outcome` לא יכול להבדיל בין משאב שלנו למשאב קיים באותו שם.** לכן הבדיקה המוקדמת לפני ה-Saga עוצרת בקשה
  שהמשאבים שלה כבר קיימים (`plan.md`, שאלה 5).

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
| `steps[]` | `key`, `kind`, `status`, `step_input`, `result`, `obtained_by`, `error` |

- **השמירה ב-Redis כבר משלב 1** (S4). ה-record נכתב לפני כל צעד, מיד כשיש תוצאה, ובסוף הצעד.
- **`heartbeat_at`:** ה-pod שמריץ את ה-Saga מעדכן אותו כל כמה שניות (קונפיג).
- **`obtained_by` לכל תוצאה:** `kept` (מ-`keep_result`) או `found` (מ-`find_outcome`). בביטול של תוצאה `found` נרשם
  WARNING.
- **סודות לא נכנסים ל-record:** הסיסמה של `default_user` ופרטי הגישה לקלאסטרים לא חלק מ-`step_input`. הצעד
  מקבל אותם מהקונפיג או מה-registry בזמן הריצה. סיסמאות של יוזרי DB כן נכנסות (5.3).

## 5א. Redis: מפתחות, נעילה וקריסה

**כל מפתח מתחיל ב-prefix מהקונפיג,** כי ה-Redis של הארגון מתיר למשתמש רק prefix מסוים. כל המפתחות נבנים במקום
אחד (`RedisKeys`), כך שאי אפשר לכתוב מפתח מחוץ ל-prefix.

| מפתח | סוג | תוכן |
|---|---|---|
| `{prefix}saga:{saga_id}` | string (JSON) | ה-saga record. TTL מהקונפיג אחרי שה-Saga הסתיים, כדי ששאילתת הסטטוס תענה עוד זמן מה |
| `{prefix}sagas:unfinished` | set | מזהי ה-Sagas שעוד רצים, לזיהוי אחרי קריסה |
| `{prefix}lock:{cluster}/{db}` | string | ה-`saga_id` שמחזיק בנעילה |

- **נעילה:** `SET NX` בלי TTL. שחרור רק על ידי מי שמחזיק בה, בסקריפט Lua שבודק את ה-`saga_id` לפני המחיקה. אם ה-DB
  נעול, ממתינים עד ה-timeout מהקונפיג, ואז `rejected` עם `database_locked`.
- **קריסה (D5):** pod אחר מוצא ב-`sagas:unfinished` Saga ב-`running` שה-`heartbeat_at` שלו ישן מהסף בקונפיג. הוא
  מסמן אותו `requires_manual_intervention`, רושם CRITICAL, ו**לא משחרר את הנעילה**. כך DB במצב חלקי לא משתנה עד
  שמישהו מטפל בו.
- **relay שלא זמין (הוחלט):** גם הבדיקה (`find_outcome`) לא מגיעה לקלאסטר, ולכן התוצאה נשארת לא ידועה וה-Saga
  עובר להתערבות ידנית עם הנעילה. לא מבטלים לבד, כי גם "לא נשלח" לא אמין: חיבור מוצפן שנשבר אחרי השליחה (למשל
  `SSLEOFError`) נראה בדיוק כך, גם בלי בדיקת תעודות.
- **שחרור ידני של Saga שנעצר:**
  1. קוראים את ה-record (`{prefix}saga:{saga_id}`): אילו צעדים `done`, איזה `unresolved`, ומה הקלט והתוצאה שלהם.
  2. בודקים בקלאסטר מה באמת קיים (לפי השמות שבקלט), ומשלימים או מבטלים ידנית.
  3. מוחקים את הנעילה (`{prefix}lock:{cluster}/{db}`), רק אחרי שהקלאסטר במצב נקי או מלא.
  כלי לזה (endpoint או פקודה) ייבנה בהמשך. עד אז זה נעשה ב-`redis-cli` של מי שמורשה.
- **Saga שהצליח אבל השמירה האחרונה שלו נכשלה:** הנעילה כבר שוחררה, אבל ב-Redis ה-record נשאר `running`. בדיקת
  הקריסה תסמן אותו להתערבות ידנית. מי שבודק ימצא שכל הצעדים `done` והקלאסטר מלא, ויסגור אותו.
- **שגיאות של השמירה (Redis) הן לא שגיאות של הפרויקט.** אסור לעטוף אותן ב-`RedisEnterpriseServicesError`, כדי
  שהמנוע לא יחשוב שהן כישלון של צעד ויבטל וישחרר נעילה כשהוא לא יכול לכתוב את ה-record. הן עולות, וה-Saga נעצר
  להתערבות ידנית.
- **צעד בזמן פיצוי מסומן `compensating`.** אם ה-Saga נעצר באמצע הפיצוי, הוא נשאר `compensating`: ייתכן שהביטול
  שלו בוצע בחלקו. זה שונה מ-`unresolved`, שבו ייתכן שהצעד עצמו לא רץ.
- **צעד שכבר שמר תוצאה ונכשל, בכל שגיאה, עובר ל-`find_outcome`.** הצעד יודע מה לבדוק: יצירה ממתינה ל-action
  ומחזירה את התוצאה, ועדכון משווה את הערכים. לא נמצא ⇐ הצעד נכשל ומבוטל, כי ידוע בדיוק מה קיים.
- **pivot ששמר תוצאה ונכשל ⇐ התערבות ידנית,** כי לא מפצים pivot, וההשפעה שלו אולי קיימת.
- **Saga שלא הצליח לשמור את ה-record הראשון:** שום דבר לא נשלח לקלאסטר, ולכן הנעילה משתחררת והשגיאה עולה.
- **צעד שנשאר `running` כש-Saga נעצר** (הפסקה, תקלה ב-store, באג) מסומן `unresolved`.
- **כישלון ידוע אחרי תוצאה לא ידועה** (למשל "השם כבר קיים" אחרי timeout) נבדק שוב ב-`find_outcome`. אם המשאב
  עדיין לא נמצא, ואין לצעד תוצאה שמורה, ה-Saga עובר להתערבות ידנית, כי ייתכן שהבקשה הראשונה בוצעה. אם יש תוצאה
  שמורה, ידוע בדיוק מה קיים, והצעד נכשל ומבוטל רגיל.
- **משתמש ה-ACL של השירות:** `+@all -@dangerous +info ~{prefix}*`: כל הפקודות חוץ מהמסוכנות, `INFO` בנוסף, ורק
  מפתחות תחת ה-prefix. כמה prefixes: עוד `~{prefix2}*`. הסיסמה מ-Secret בלבד.
- **הספרייה:** `redis-py`, סינכרונית, עם Lua ו-ACL (שם משתמש וסיסמה).

## המנוע גנרי לגמרי

המנוע מכיר רק `SagaStep`, `StepKind` ו-`SagaPlan`. הוא לא יודע מה זה יצירה, משאב או DB, ולכן הוא מריץ כל
צירוף: יצירה, עדכון ומחיקה, pivot, וצעדים שניתנים לחזרה. ההבדל בין הפעולות נמצא רק בצעדים ובסוג שלהם:

| סוג | בכשל של צעד מאוחר יותר | בכשל שלו |
|---|---|---|
| `COMPENSATABLE` | מבוטל בסדר הפוך | ניסיונות, ואז ביטול של מה שלפניו |
| `PIVOT` | לא מבוטל. אחריו רק קדימה | ניסיונות, ואז ביטול של מה שלפניו (הוא עצמו לא בוצע) |
| `RETRIABLE` | - (אחרי ה-pivot) | ניסיונות עד הצלחה, ואז התערבות ידנית |

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
ב-Redis (סעיף 5א), כך ש:
- שני pods לא ירוצו על אותו DB (סעיף 10).
- כל pod יכול לענות ל-`GET /v1/operations/{trace_id}`, כי ה-record ב-Redis.
- pod שקרס משאיר Saga ב-`running` שה-heartbeat שלו ישן. pod אחר מזהה אותו בעלייה או בבדיקה תקופתית, ומסמן
  `requires_manual_intervention`. הנעילה נשארת (D5).

## 7. ניסיונות חוזרים (הוחלט)

שתי מדיניות, מהקונפיג: אחת לצעדים (שגיאה זמנית, ולא נמצא אחרי תוצאה לא ידועה), ואחת לפיצויים. לכל אחת מספר
ניסיונות ו-backoff. השגיאות שנחשבות זמניות (`busy`, `wrong_cluster_state_id`) גם הן בקונפיג.

## 8. החלטות

| # | נושא | החלטה |
|---|---|---|
| S1 | קלט שתלוי בצעד קודם | התוכנית בונה את הקלט מה-context (`build_input`, סעיף 3). הצעד לא מכיר את ה-context |
| S2 | ספרייה או מימוש שלנו | מימוש שלנו (סעיף 6). אין Dapr או תשתית אחרת ב-OpenShift, וההמשך אחרי קריסה לא נדרש (D5) |
| S3 | ניסיונות חוזרים | שתי מדיניות מהקונפיג, לצעדים ולפיצויים (סעיף 7) |
| S4 | שמירה ונעילה | ב-Redis כבר משלב 1, `redis-py`, מפתחות תחת prefix מהקונפיג, נעילה בלי TTL ו-`heartbeat_at` לזיהוי קריסה (סעיף 5א) |

## מקורות

- [Saga pattern, Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Richardson, Managing data consistency using sagas (slides)](https://backiee.wasmer.app/https_www_slideshare_net/slideshow/microcph-managing-data-consistency-in-a-microservice-architecture-using-sagas/146951030)
- [Saga timeouts: the compensation path most teams never test](https://dev.to/gabrielanhaia/saga-timeouts-the-compensation-path-most-teams-never-test-1dok)
- [Compensations need idempotency keys too](https://codemia.io/archive/saga-pattern-for-distributed-transactions)
- [Saga orchestration pattern (2026)](https://appscale.blog/en/blog/microservices-pattern-saga-orchestration-2026)
- [Durable workflow engines comparison](https://dev.to/mahdi0shamlou/mahdi-shamlou-durable-workflow-engines-comparison-temporal-dbos-transact-prefect-custom-3a6a)
