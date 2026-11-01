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

    def find_outcome(
        self, *, step_input: TInput, kept: TResult | None, keep_found: KeepResult[TResult]
    ) -> TResult | None: ...

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
  `None` אומר שהשינוי לא נמצא בקלאסטר. כשיש `kept`, הוא מחזיר `None` רק אם הרצה חוזרת של הצעד בטוחה, כי אחרי
  שגיאה זמנית המנוע מריץ אותו שוב.
- **`keep_found`** נקרא ב-`find_outcome` ברגע שנמצא משאב, לפני ההמתנה, כמו `keep_result` ב-`execute`. כך משאב שנמצא
  לפי שם, ונכשל בהמתנה (למשל DB ב-`creation-failed`), נשאר תוצאה של הצעד ומבוטל.
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
| מחיקת user | כתובת קלאסטר + uid | - | האם היוזר כבר לא קיים | **retriable**, בסוף התוכנית, `404` = הצלחה, אין פיצוי (`saga.md` 7.6) |

## 3. קלט שתלוי בצעד קודם

ל-role צריך את ה-uid של ה-DB, ולמשתמש את ה-uid של ה-role. התוכנית בונה את הקלט של כל צעד **כשמגיע תורו**,
מתוך ה-context:

```python
PlannedStep(
    key="cluster1/role/db1-app-role/create",  # ייחודי בתוכנית
    step=create_role,  # SagaStep[TInput, TResult]
    build_input=lambda context: ...,  # Callable[[SagaContext], TInput]
)
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
| `ClusterRequestError` זמני (`409 busy`, `db_busy`, `wrong_cluster_state_id`, מהקונפיג של הקלאסטר) | ניסיון חוזר לפי מדיניות. אם לצעד יש תוצאה שמורה, קודם `find_outcome`: נמצא ⇐ `done`, לא נמצא ⇐ ניסיון חוזר |
| `ClusterRequestError` אחר | הצעד נכשל ⇐ פיצוי |
| `InvalidEdgeRequestError` | הצעד נכשל ⇐ פיצוי (באג אצלנו) |
| `ClusterActionFailedError` (ה-action הסתיים ב-`failed`, `cancelled` או `aborted`) | הצעד נכשל ⇐ פיצוי. זו תוצאה ידועה, ולא מנסים שוב |
| `AmbiguousResourceError` מ-`find_outcome` (יותר ממשאב אחד באותו שם) | התערבות ידנית מיד: לא מנסים שוב ולא מפצים שום צעד, כי לא ידוע איזה משאב שלנו |
| כל שגיאה אחרת של הפרויקט (למשל `UnrestorableFieldsError`) | הצעד נכשל ⇐ פיצוי, בלי ניסיון חוזר: היא תחזור באותה צורה |
| שגיאה מתוך `find_outcome` | אותו מיון כמו בטבלה: `ClusterActionFailedError` או `DatabaseCreationFailedError` ⇐ הצעד נכשל, והוא מבוטל אם נשמרה לו תוצאה (ב-`execute` או ב-`keep_found`), `AmbiguousResourceError` ⇐ התערבות ידנית, וכל השאר ⇐ התערבות ידנית מיד, בלי לנסות את הבדיקה שוב, כי ייתכן שהפעולה בוצעה |
| כל שגיאת קצה אחרת, timeout של המתנה, או תשובה שלא נקראת (`UnreadableAnswerError`) | `find_outcome` פעם אחת: נמצא ⇐ `done`. לא נמצא, ואין לצעד תוצאה שמורה ⇐ ניסיון חוזר אחד, ומכאן כל כישלון ⇐ התערבות ידנית. לא נמצא, ויש תוצאה שמורה ⇐ התערבות ידנית: ייתכן שהבקשה עוד תגיע לקלאסטר אחרי הבדיקה, למשל `PUT` של עדכון אחרי timeout של הקצה, ואז ביטול שלא מצא מה להחזיר ישחרר את המנעול לפני שהשינוי נכנס |
| נגמרו הניסיונות | הצעד נכשל ⇐ פיצוי. אם בדרך הייתה תוצאה לא ידועה ⇐ התערבות ידנית |

- **רק ה-`keep_result` הראשון של צעד נשמר,** כך שניסיון חוזר לא מחליף את ה-snapshot הראשון. אחרי תוצאה לא ידועה
  המנוע קורא קודם ל-`find_outcome`, ורק אם לא נמצא כלום, ואין לצעד תוצאה שמורה, הוא מריץ את `execute` שוב. אחרי
  שגיאה זמנית הוא מריץ שוב גם עם תוצאה שמורה, אם לא נמצא כלום.
- **`find_outcome` מחזיר תוצאה רק אחרי ההמתנה של הצעד.** אם יש `kept` (ה-`POST` ענה), הוא סומך עליו ולא מחפש
  לפי שם. אחרת הוא מחפש לפי שם. בשני המקרים הוא מחכה לסיום (`wait_created`) לפני שהוא מחזיר, כדי שה-Saga לא ידווח
  הצלחה בזמן שה-DB עוד `pending`, ושהביטול לא ירוץ במקביל לפעולה שעוד רצה. משאב שנמצא לפי שם בלי `action_uid`
  (user, role, ACL) לא נמתן, כי ה-action שלו לא ידוע. אם הוא עוד רץ, הצעד הבא יקבל `busy`, עם ניסיון חוזר.
- **ה-record שומר איך התוצאה הושגה:** מ-`keep_result` או מחיפוש לפי שם. בביטול של משאב שנמצא לפי שם נרשם WARNING,
  כי הבדיקה המוקדמת לא מכסה את הזמן שבינה לבין ה-`POST`.
- **`find_outcome` לא יכול להבדיל בין משאב שלנו למשאב קיים באותו שם.** לכן הבדיקה המוקדמת לפני ה-Saga עוצרת בקשה
  שהמשאבים שלה כבר קיימים (`plan.md`, שאלה 5).

5. **פיצוי:** כל צעד `COMPENSATABLE` **שיש לו תוצאה** ב-context, בסדר הפוך. ניסיונות חוזרים רק על שגיאה זמנית או תוצאה
   לא ידועה (הביטול idempotent). כישלון ידוע, או שהניסיונות נגמרו ⇐ `compensation_failed`,
   וה-Saga מסומן `requires_manual_intervention` (סעיף 9).
6. **נקודת האל-חזור:** הצעד הראשון שאינו הפיך (pivot, או retriable כשאין pivot).
   - **לפני שהוא הצליח:** כשל שלו, כשהוא לא בוצע, מבטל את מה שלפניו.
   - **אחרי שהוא הצליח:** אין פיצוי. כשל ⇐ ניסיונות חוזרים, ואז התערבות ידנית.
7. **נעילה:** המנוע לוקח את נעילת ה-DB לפני הצעד הראשון ומשחרר בסוף, כולל אחרי פיצוי (סעיף 10).
8. **קריסה:** לפי D5. בעלייה לא ממשיכים ולא מבטלים, רק מסמנים להתערבות ידנית.

## 5. Saga record

| שדה | תוכן |
|---|---|
| `saga_id` | ה-trace ID של הבקשה |
| `status` | `running`, `succeeded`, `rolled_back`, `requires_manual_intervention` |
| `steps[]` | `key`, `kind`, `status`, `step_input`, `result`, `obtained_by`, `error` |
| `stopped_at` | המפתח של הצעד שעצר את ה-Saga, או `null`. נשמר גם כשהצעד עצמו בוטל אחר כך (צעד ששמר תוצאה ונכשל) |
| `steps[].compensation_error` | השגיאה האחרונה של הביטול, בנפרד מ-`error`, כדי שהסיבה שהצעד נכשל לא תידרס |
| `steps[].error` | השגיאה האחרונה של הצעד, כשדות: `code` (הקוד שלנו), `message`, ו-`remote_code` (הקוד שהמערכת המרוחקת נתנה, למשל `name_already_exists` של הקלאסטר). המנוע לא מכיר את הקלאסטר: הוא קורא `remote_code()` מהשגיאה, וכל שגיאה שיש לה קוד מרוחק מחזירה אותו |
| `heartbeat_at` | עוד לא נבנה, נבנה באבן 8ד |

- **השמירה ב-Redis כבר משלב 1** (S4). ה-record נכתב לפני כל צעד, מיד כשיש תוצאה, ובסוף הצעד.
- **`heartbeat_at`** (עוד לא נבנה, נבנה באבן 8ד): ה-pod שמריץ את ה-Saga מעדכן אותו כל כמה שניות (קונפיג).
- **`obtained_by` לכל תוצאה:** `kept` (מ-`keep_result`) או `found` (מ-`find_outcome`). בביטול של תוצאה `found` נרשם
  WARNING.
- **סודות לא נכנסים ל-record:** הסיסמה של `default_user` ופרטי הגישה לקלאסטרים לא חלק מ-`step_input`. הצעד
  מקבל אותם מהקונפיג או מה-registry בזמן הריצה. סיסמאות של יוזרי DB כן נכנסות (5.3).

## 5א. Redis: מפתחות, נעילה וקריסה

**כל מפתח מתחיל ב-prefix מהקונפיג,** כי ה-Redis של הארגון מתיר למשתמש רק prefix מסוים. כל המפתחות נבנים במקום
אחד (`RedisKeys`), כך שאי אפשר לכתוב מפתח מחוץ ל-prefix.

`res:` ו-`{state}` הם ה-prefix וה-hash tag מהקונפיג, והסוגריים המסולסלים הם חלק מהמפתח.

| מפתח | סוג | תוכן |
|---|---|---|
| `res:{state}saga:{saga_id}` | string (JSON) | ה-saga record. TTL מהקונפיג אחרי שה-Saga הסתיים, כדי ששאילתת הסטטוס תענה עוד זמן מה |
| `res:{state}sagas:unfinished` | set | מזהי ה-Sagas שעוד רצים, לזיהוי אחרי קריסה |
| `res:{state}lock:{cluster}/{db}` | string | ה-`saga_id` שמחזיק בנעילה |
| `res:{state}lock:{cluster}/user/{user}` | string | כנ"ל, לכל יוזר שהפקודה יוצרת. שמות ה-ACL וה-role נגזרים משם ה-DB, ולכן הנעילה של ה-DB מכסה אותם |
| `res:{state}operation:{trace_id}` | string (JSON) | מה ששאילתת הסטטוס מחזירה (`service-api.md` סעיף 8). TTL מהקונפיג כשהפעולה `succeeded`, `rejected` או `rolled_back`. `running` ו-`requires_manual_intervention` בלי TTL |
| `res:{state}operations:open` | set | ה-`trace_id` של פעולות שעוד לא הסתיימו (`running`, `requires_manual_intervention`), לזיהוי אחרי קריסה |

- **נעילה:** `SET` בלי TTL. סקריפט Lua אחד נועל את כל המפתחות של ה-Saga, או אף אחד מהם אם אחד תפוס (ב-AA יש כמה).
  שחרור רק על ידי מי שמחזיק בה, בסקריפט Lua שבודק את ה-`saga_id` לפני המחיקה.
- **`before_start`:** `SagaExecutor.run` מקבל בדיקה שרצה אחרי הנעילה ולפני הצעד הראשון ולפני שה-record נשמר. נכשלה ⇐
  הנעילה משתחררת והשגיאה עולה, ושום צעד לא רץ. כך הבדיקה המוקדמת רצה תחת הנעילה, בלי שהנעילה תאפשר לנעול פעמיים. אם ה-DB
  נעול, ממתינים עד ה-timeout מהקונפיג, ואז `rejected` עם `database_locked`.
- **קריסה (D5, עוד לא נבנה, נבנה באבן 8ד):** pod אחר מוצא ב-`sagas:unfinished` Saga ב-`running` שה-`heartbeat_at`
  שלו ישן מהסף בקונפיג. הוא מסמן אותו `requires_manual_intervention`, רושם CRITICAL, ו**לא משחרר את הנעילה**. כך DB
  במצב חלקי לא משתנה עד שמישהו מטפל בו.
- **relay שלא זמין (הוחלט):** גם הבדיקה (`find_outcome`) לא מגיעה לקלאסטר, ולכן התוצאה נשארת לא ידועה וה-Saga
  עובר להתערבות ידנית עם הנעילה. לא מבטלים לבד, כי גם "לא נשלח" לא אמין: חיבור מוצפן שנשבר אחרי השליחה (למשל
  `SSLEOFError`) נראה בדיוק כך, גם בלי בדיקת תעודות.
- **שחרור ידני של Saga שנעצר:**
  1. קוראים את ה-record (`res:{state}saga:{saga_id}`): אילו צעדים `done`, איזה `unresolved`, ומה הקלט והתוצאה שלהם.
  2. בודקים בקלאסטר מה באמת קיים (לפי השמות שבקלט), ומשלימים או מבטלים ידנית.
  3. מוחקים את כל מפתחות הנעילה שה-`saga_id` מחזיק (`res:{state}lock:{cluster}/{db}`, ו-`res:{state}lock:{cluster}/user/{user}`
     לכל יוזר), רק אחרי שהקלאסטר במצב נקי או מלא.
  כלי לזה (endpoint או פקודה) ייבנה בהמשך. עד אז זה נעשה ב-`redis-cli` של מי שמורשה.
- **Saga שהצליח אבל השמירה האחרונה שלו נכשלה:** הנעילה כבר שוחררה, אבל ב-Redis ה-record נשאר `running`. בדיקת
  הקריסה תסמן אותו להתערבות ידנית. מי שבודק ימצא שכל הצעדים `done` והקלאסטר מלא, ויסגור אותו.
- **שגיאות של השמירה (Redis) הן לא שגיאות של הפרויקט.** אסור לעטוף אותן ב-`RedisEnterpriseServicesError`, כדי
  שהמנוע לא יחשוב שהן כישלון של צעד ויבטל וישחרר נעילה כשהוא לא יכול לכתוב את ה-record. הן עולות, וה-Saga נעצר
  להתערבות ידנית.
- **צעד בזמן פיצוי מסומן `compensating`.** אם ה-Saga נעצר באמצע הפיצוי, הוא נשאר `compensating`: ייתכן שהביטול
  שלו בוצע בחלקו. זה שונה מ-`unresolved`, שבו ייתכן שהצעד עצמו לא רץ.
- **צעד שכבר שמר תוצאה ונכשל, בכל שגיאה, עובר ל-`find_outcome`.** הצעד יודע מה לבדוק: יצירה ממתינה ל-action
  ומחזירה את התוצאה, ועדכון משווה את הערכים. לא נמצא ⇐ הצעד לא רץ שוב (יצירה שנייה הייתה יוצרת משאב שאף אחד
  לא מבטל), אלא נכשל ומבוטל, כי ידוע בדיוק מה קיים. חוץ משני מקרים: אחרי שגיאה זמנית הקלאסטר אמר שלא ביצע, ולכן
  הצעד רץ שוב. אחרי תוצאה לא ידועה הבקשה אולי עוד תגיע לקלאסטר, ולכן ⇐ התערבות ידנית (5א).
  נבדק מול cluster1: `PUT` של עדכון קיבל `409 db_busy` אחרי שה-snapshot נשמר, ובלי זה כל ה-Saga בוטל.
- **pivot או retriable ששמר תוצאה ונכשל ⇐ התערבות ידנית, והצעד מסומן `unresolved`** (אחרי שגיאה זמנית: רק כשנגמרו
  הניסיונות), כי אין לו פיצוי, וההשפעה שלו אולי קיימת.
- **ה-Redis של המצב נחשב זמין** (Redis Enterprise של צוות אחר, הוחלט 2026-10-29). אין טיפול בנפילה שלו או בתשובה
  שאבדה: אין שחרור נעילה כשהשמירה הראשונה נכשלת, ואין ניסיון חוזר של פקודה. שגיאה שלו עוצרת את ה-Saga.
- **צעד שנשאר `running` כש-Saga נעצר** (הפסקה, תקלה ב-store, באג) מסומן `unresolved`.
- **אחרי תוצאה לא ידועה, כל מה שאינו הצלחה ⇐ התערבות ידנית** (הוחלט 2026-10-29). המנוע בודק פעם אחת. לא נמצא ⇐
  ניסיון חוזר אחד. כל כישלון שאחריו, ידוע או זמני, עוצר את ה-Saga, כי ייתכן שהבקשה הראשונה בוצעה. כך אין בדיקות
  חוזרות בתוך ניסיונות חוזרים.
- **משתמש ה-ACL של השירות:** `+@all -@dangerous +info ~{prefix}*`: כל הפקודות חוץ מהמסוכנות, `INFO` בנוסף, ורק
  מפתחות תחת ה-prefix. כמה prefixes: עוד `~{prefix2}*`. הסיסמה מ-Secret בלבד.
- **הספרייה:** `redis-py`, סינכרונית, עם Lua ו-ACL (שם משתמש וסיסמה).
- **שמירת ה-record** וההוספה ל-`sagas:unfinished` (או ההוצאה ממנו בסוף, עם ה-TTL) נעשות יחד בסקריפט Lua אחד.
- **קונפיג:** `config/state.yaml` (host, port, user, prefix, hash tag, timeout של socket, TTL, זמן ההמתנה לנעילה). הסיסמה
  רק מ-`RES_STATE__PASSWORD`.
- **כל המפתחות עם אותו hash tag אחרי ה-prefix** (`res:{state}saga:...`), כדי שהסקריפטים יעבדו גם ב-DB עם כמה shards.
- **רשומת הפעולה נפרדת מה-saga record.** `rejected` (לפני שה-Saga התחיל) ועץ ה-DB הם לא מושגים של ה-Saga, ולכן המנוע
  נשאר גנרי. הרשומה (`operations/`) והממשק `OperationStore` משמשים כל פקודה: יצירה, עריכה ומחיקה.
  התשובה המיידית לשגיאה היא אותה רשומה, עם `rejected` (החוזה, סעיף 8).
- **פעולה מתחילה בסקריפט Lua אחד:** אם כבר יש רשומה לאותו trace, הסקריפט מחזיר אותה ולא כותב. אחרת הוא שומר
  `running` ומוסיף ל-`operations:open`. כך שתי בקשות עם אותו trace במקביל לא מתחילות שתי ריצות (8ג).
- **פעולה פתוחה ב-`operations:open`,** בדיוק כמו Saga ב-`sagas:unfinished`. ייתכן ש-pod יקרוס לפני שה-Saga התחיל
  (בבדיקות שרצות ברקע), או אחרי שה-Saga הסתיים ולפני שהפעולה נשמרה. בשני המקרים רק ה-set הזה מראה שהפעולה נשארה
  פתוחה. בדיקת הקריסה (8ד) תסרוק את שני ה-sets.
- **רק Saga שהצליח או בוטל מקבל TTL ויוצא מ-`sagas:unfinished`.** Saga להתערבות ידנית נשמר בלי TTL ונשאר ב-set,
  כי ה-record שלו הוא הצעד הראשון בשחרור הידני, והנעילה שלו נשארת.
- **נבדק מול ה-Redis של הסביבה המקומית** (2026-10-29): Saga שהצליח ושבוטל נשמרו עם TTL, יצאו מ-`sagas:unfinished`,
  והנעילה שוחררה. DB נעול ⇐ המתנה, ואז `database_locked` בלי אף קריאה לקלאסטר.

## המנוע גנרי לגמרי

המנוע מכיר רק `SagaStep`, `StepKind` ו-`SagaPlan`. הוא לא יודע מה זה יצירה, משאב או DB, ולכן הוא מריץ כל
צירוף: יצירה, עדכון ומחיקה, pivot, וצעדים שניתנים לחזרה. ההבדל בין הפעולות נמצא רק בצעדים ובסוג שלהם:

| סוג | בכשל של צעד מאוחר יותר | בכשל שלו |
|---|---|---|
| `COMPENSATABLE` | מבוטל בסדר הפוך | ניסיונות, ואז ביטול של מה שלפניו |
| `PIVOT` | לא מבוטל. אחריו רק קדימה | ניסיונות, ואז ביטול של מה שלפניו (הוא עצמו לא בוצע). אם שמר תוצאה ⇐ התערבות ידנית |
| `RETRIABLE` | - (בסוף התוכנית, אחרי ה-pivot אם יש) | ניסיונות חוזרים. כשהם נגמרו: אם הוא הראשון שאינו הפיך ולא בוצע ⇐ ביטול של מה שלפניו. אחרת ⇐ התערבות ידנית |

**המנוע לא מכיר את השגיאות של הקלאסטר.** הוא מקבל `FailureClassifier` מבחוץ, שממיין כל שגיאה לאחת מארבע
קטגוריות: זמנית, נכשלה, תוצאה לא ידועה, התערבות ידנית. המימוש לקלאסטר הוא `ClusterFailureClassifier`
(`steps/failure_classifier.py`), לפי הטבלה בסעיף 4. התיקייה `saga/` לא מייבאת שום שגיאה של הקלאסטר או של שירות הקצה.

**שלוש תיקיות, בכיוון אחד:**

| תיקייה | מה יש בה | מייבאת |
|---|---|---|
| `saga/contract/` | מה שמבחוץ מממשים או מקבלים: `SagaStep`, `StepKind`, `KeepResult`, `Failure` ו-`FailureClassifier`, `DatabaseLock`, `SagaStateRepository`, וה-record | כלום מתוך `plan` או `engine` |
| `saga/plan/` | בניית התוכנית: `SagaPlan`, `PlannedStep`, `RunnableStep`/`PreparedStep`, `SagaContext` | `contract` |
| `saga/engine/` | ההרצה: `SagaExecutor`, `StepRunner`, `Compensator`, `StepRecorder`, וההמתנה בין ניסיונות | `contract`, `plan` |

הכיוונים נאכפים ב-`import-linter`, שרץ ב-pre-commit. כל הכללים, לכל השכבות, ב-`pyproject.toml`. כלל אחד מסדר את כל החבילות ברמה העליונה, וחבילה חדשה נכשלת בו עד שנותנים לה מקום. חבילות באותה רמה, שמחוברות ב-`|`, לא מייבאות זו מזו.

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
  `requires_manual_intervention`. הנעילה נשארת (D5). עוד לא נבנה, נבנה באבן 8ד.

## 7. ניסיונות חוזרים (הוחלט)

שתי מדיניות, מהקונפיג: אחת לצעדים (שגיאה זמנית, ולא נמצא אחרי תוצאה לא ידועה), ואחת לפיצויים (רק שגיאה זמנית או
תוצאה לא ידועה; כישלון ידוע לא ינסה שוב). לכל אחת מספר
ניסיונות ו-backoff. השגיאות שנחשבות זמניות (`busy`, `db_busy`, `wrong_cluster_state_id`) הן ידע על הקלאסטר, ולכן הן בקונפיג
של הקלאסטר (`config/cluster.yaml`), ולא של המנוע.

**זמן ההמתנה המרבי של צעד:** כל ניסיון של `execute` יכול לחכות ל-action (`wait_created`), ואחריו בדיקה אחת
(`find_outcome`) שגם היא יכולה לחכות. הבדיקה לא חוזרת על עצמה (5א). לכן במקרה הגרוע: ניסיונות × שתי המתנות ל-action,
ועוד ה-backoff. עם הקונפיג הנוכחי (3 ניסיונות) זה עד 6 המתנות ל-action בצעד אחד.

## 8. החלטות

| # | נושא | החלטה |
|---|---|---|
| S1 | קלט שתלוי בצעד קודם | התוכנית בונה את הקלט מה-context (`build_input`, סעיף 3). הצעד לא מכיר את ה-context |
| S2 | ספרייה או מימוש שלנו | מימוש שלנו (סעיף 6). אין Dapr או תשתית אחרת ב-OpenShift, וההמשך אחרי קריסה לא נדרש (D5) |
| S3 | ניסיונות חוזרים | שתי מדיניות מהקונפיג, לצעדים ולפיצויים (סעיף 7) |
| S4 | שמירה ונעילה | ב-Redis כבר משלב 1, `redis-py`, מפתחות תחת prefix מהקונפיג, נעילה בלי TTL ו-`heartbeat_at` לזיהוי קריסה (סעיף 5א; ה-heartbeat עוד לא נבנה) |

## מקורות

- [Saga pattern, Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Richardson, Managing data consistency using sagas (slides)](https://backiee.wasmer.app/https_www_slideshare_net/slideshow/microcph-managing-data-consistency-in-a-microservice-architecture-using-sagas/146951030)
- [Saga timeouts: the compensation path most teams never test](https://dev.to/gabrielanhaia/saga-timeouts-the-compensation-path-most-teams-never-test-1dok)
- [Compensations need idempotency keys too](https://codemia.io/archive/saga-pattern-for-distributed-transactions)
- [Saga orchestration pattern (2026)](https://appscale.blog/en/blog/microservices-pattern-saga-orchestration-2026)
- [Durable workflow engines comparison](https://dev.to/mahdi0shamlou/mahdi-shamlou-durable-workflow-engines-comparison-temporal-dbos-transact-prefect-custom-3a6a)
