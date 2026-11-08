# יצירת DB: איך בקשה רצה

מה קורה מרגע ש-`POST /v1/databases/create` מגיע ועד שהתוצאה נשמרת. החוזה עצמו (שדות, קודים): `contracts/service-api.md`.
המנוע, ה-Redis וההתאוששות: `saga-engine-and-state.md`.

**בנוי:** יצירה באתר אחד. **לא בנוי:** `planned.md`.

---

## 1. המסלול

![קבלה](../diagrams/12-flow-admission.drawio.svg)

```
POST /v1/databases/create
 ├─ ולידציה של הגוף (Pydantic) ו-traceparent           ⇐ 422 מיד
 ├─ OperationAcceptance.accept
 │   ├─ יש פעולה לאותו trace?                           ⇐ 200 עם המצב שלה
 │   ├─ CreationPreparation: שם, קלאסטר, ברירות מחדל     ⇐ 422 / 500 מיד
 │   ├─ התחלה אטומית: running + heartbeat
 │   └─ העברה ל-ThreadPoolTaskRunner                          ⇐ 202
 └─ ברקע: CreationExecution
     ├─ SingleSiteCreationPlanner: תוכנית צעדים
     ├─ SagaExecutor: נעילה ⇐ בדיקת שמות פנויים ⇐ צעדים
     └─ CreationOutcome: התוצאה ⇐ OperationStore
```

| רכיב | תיקייה | מה הוא עושה |
|---|---|---|
| `DatabaseCreation` | `creation/` | מה שה-route קורא לו: מעביר ל-`OperationAcceptance.accept` את ההכנה, שרצה רק אחרי החיפוש לפי trace |
| `OperationAcceptance` | `operations/` | הסדר המשותף לכל פקודה: חיפוש לפי trace, הכנה, התחלה אטומית, העברה לרקע (`saga-engine-and-state.md` סעיף 8) |
| `CreationPreparation` | `creation/` | כל מה שאפשר לבדוק בלי הקלאסטר |
| `CreationExecution` | `creation/` | הריצה ברקע, עד רשומת הפעולה הסופית |
| `SingleSiteCreationPlanner` | `planning/` | הבקשה ⇐ תוכנית צעדים ומפתחות נעילה |
| `CreationOutcome` | `creation/` | ה-saga record ⇐ הפעולה: עץ ה-DB, או השגיאה ומה שלא בוטל |

![שכבת creation](../diagrams/04-layer-creation.drawio.svg)

![שכבת planning](../diagrams/05-layer-planning.drawio.svg)

**נקודת ההרכבה:** `composition/` (`services.py`, `cluster_wiring.py`) בונה את כל המחלקות הקונקרטיות. רק `app` מעליה.

---

## 2. ההכנה (לפני `202`)

![קלאסטר וברירות מחדל](../diagrams/13-flow-cluster-and-defaults.drawio.svg)

1. **שם ה-DB** לפי `config/naming.yaml`. אחרת `invalid_name`.
2. **הקלאסטר** (`ClusterResolver`) מתוך `config/clusters.yaml`: רשימה שטוחה, ולכל קלאסטר `name`, `network`,
   `environment`, `site`, `type` ו-`api_url`. ההתאמה היא לפי השדות, ולכן אין היררכיה קבועה בין רשת, סביבה ואתר.
   - `dedicated`: הקלאסטר עם אותם רשת, סביבה, אתר ושם.
   - `generic`: כל הקלאסטרים ה-generic באותם רשת, סביבה ואתר הם מועמדים, ו-`ClusterChooser` בוחר. המימוש היום,
     `SingleCandidateChooser`, דורש מועמד אחד בדיוק. כמה ⇐ `configuration_error`. בחירה בין כמה: `planned.md`.
   - אין קלאסטר מתאים ⇐ `unknown_cluster`.
3. **ברירות מחדל** (`DatabaseDefaults`, `config/database_defaults.yaml`):

   ```yaml
   database_defaults:
     values: {version: "8.4", replication: true, data_persistence: aof, ...}
     overrides:
       - when: {environment: DEV}
         values: {replication: false}
   ```

   - הסדר: `values`, אחריהן כל דריסה שה-`when` שלה מתאים לקלאסטר שנבחר (לפי הסדר ברשימה), ובסוף השדות שהבקשה
     שלחה ולא כ-`null`. התוצאה עוברת ולידציה ב-`NewDatabase`.
   - `when` מתאים לפי כל צירוף של `network`, `environment`, `site`, `type` ו-`cluster` (השם).
   - הדריסה היא לפי שדה ברמה העליונה. לשדות של ה-DB אין אובייקטים מקוננים שצריך למזג.
   - בעלייה: תווית לא מוכרת, או ערך שלא עובר את `DatabaseOptions`, עוצרים את השירות.

כל מה שבשלב הזה לא נוגע בקלאסטר, ולכן כשל בו הוא תשובה מיידית, ושום דבר לא נשמר.

---

## 3. התוכנית

![יצירה](../diagrams/10-seq-create-single-site.drawio.svg)

| # | מפתח | צעד | מה נשלח | ביטול |
|---|---|---|---|---|
| 1 | `database` | `CreateResourceStep` | `POST /v1/bdbs`, ואז המתנה ל-`active` | `DELETE`, ואז המתנה ל-404 |
| 2 | `acl/{user}` | `CreateResourceStep` | `POST /v1/redis_acls` `{name: {db}-{user}-acl, acl}` | `DELETE` |
| 3 | `role/{user}` | `CreateResourceStep` | `POST /v1/roles` `{name: {db}-{user}-role, management: db_viewer, resources: [ה-DB]}` | `DELETE` |
| 4 | `user/{user}` | `CreateResourceStep` | `POST /v1/users` `{name, password, role_uids: [ה-role]}` | `DELETE` |
| 5 | `permissions` | `DatabaseUpdate` | `PUT /v1/bdbs/{uid}` עם `roles_permissions`: זוג role ↔ ACL לכל יוזר | `PUT` של הרשימה הקודמת |

- צעדים 2–4 חוזרים לכל יוזר, לפי הסדר בבקשה. צעד 5 אחד לכל היוזרים, ורק כשיש יוזרים.
- כל הצעדים הפיכים. אין pivot, ולכן כשל ודאי בכל שלב מחזיר את הקלאסטר למצב שלפני הבקשה.
- ה-role נוצר אחרי ה-DB כי `resources` חייב uid של DB קיים, והיוזר אחרי ה-role כי הוא חייב role.
- ה-uids עוברים בין צעדים דרך ה-`SagaContext` (`saga-engine-and-state.md` סעיף 3).
- שמות ה-ACL וה-role וה-`management` מ-`config/user_resources.yaml`.
- ביצירת ACL, role ו-user, אם התשובה כוללת `action_uid`, הצעד מחכה ל-`/v1/actions/{uid}` עד `completed`.
- גוף ה-DB כולל גם `default_user: true`, `authentication_redis_pass` (הסיסמה של `default_user` מ-Secret) ו-`tags`
  (`database.default_tags`). הסיסמה מתווספת רק ברגע השליחה, ולא נכנסת לקלט של הצעד או ל-record.

**שמות.** כל ACL ו-role שייכים ליוזר אחד ב-DB אחד. שם יוזר עם `-` נדחה בולידציה, כי אחרת שתי בקשות שונות יכולות לקבל
אותו שם נגזר (DB `orders` עם יוזר `app-x`, ו-DB `orders-app` עם יוזר `x`).

**נעילה.** מפתחות `{cluster}/{db}` ו-`{cluster}/user/{user}` לכל יוזר. שמות ה-ACL וה-role נגזרים משם ה-DB, ולכן
הנעילה של ה-DB מכסה אותם.

**בדיקת שמות פנויים** (`NameAvailability`), כ-`check_before_start`: אחרי הנעילה ולפני הצעד הראשון. היא בודקת את ה-DB, ולכל
יוזר את השם שלו ואת שמות ה-ACL וה-role. ל-REST API אין חיפוש לפי שם, ולכן היא שולפת פעם אחת כל סוג משאב (`bdbs`,
`users`, `redis_acls`, `roles`) ומסננת בקוד. היא רצה תחת הנעילה, כי הקלאסטר לא אוכף שם DB ייחודי, ושתי בקשות שבודקות
לפני הנעילה היו עוברות יחד. ההיקף (`ChosenClusterScope`: רק הקלאסטר שנבחר) הוא ממשק נפרד, כך שאפשר להרחיב אותו
לקלאסטרים נוספים בלי לשנות את הבדיקה. שם תפוס ⇐ `name_taken`, והנעילה משתחררת.

---

## 4. התוצאה

![ביטול](../diagrams/11-seq-rollback-single-site.drawio.svg)

`CreationExecution` מתרגם כל סוף לרשומת פעולה, ושומר אותה:

| מה קרה | הפעולה |
|---|---|
| ה-Saga הצליח | `succeeded` עם עץ ה-DB (`creation_result.py`): ה-uids מהתוצאות של הצעדים |
| ה-Saga `rolled_back` או `requires_manual_intervention` | אותו סטטוס, עם `error` של הצעד שעצר (`stopped_at`), ו-`not_rolled_back` |
| שגיאה של הפרויקט לפני שה-Saga התחיל (נעילה, שם תפוס) | `rejected` עם הקוד שלה |
| שגיאה לא צפויה | אין saga record ⇐ `rejected` עם `internal_error`. יש record ⇐ כמו בסוף רגיל, מתוך ה-record. record שלא נקרא ⇐ `requires_manual_intervention` עם `internal_error` |

- **`not_rolled_back`** (`CreationOutcome`): כל צעד שנשאר `done`, `unresolved`, `compensating` או
  `compensation_failed`, עם הסוג, השם והקלאסטר מהתוכנית, וה-uid מהתוצאה. ב-`permissions` השם וה-uid הם של ה-DB.
  `error` הוא `"<code>: <message>"` של השגיאה האחרונה: של הביטול אם נכשל, אחרת של הצעד, עם הקוד הציבורי.
- **קודים ציבוריים** (`PublicErrors`, `config/operation.yaml`): כל קוד פנימי ממופה לקוד מהחוזה. קוד בלי מיפוי ⇐
  `internal_error` ו-WARNING. `cluster` ו-`cluster_error_code` נוספים רק לקודים שב-`cluster_caused_public_codes`.
- **סדר השמירה:** המנוע משחרר את הנעילה, ורק אחר כך הפעולה נשמרת.

---

## 5. בדיקות מול קלאסטר אמיתי

הזרימה נבדקה מקצה לקצה מול השירות, cluster-relay וקלאסטר מקומי:
- **הצלחה עם שני יוזרים:** חיבור בלי סיסמה ⇐ `NOAUTH`. `default` עם הסיסמה ⇐ `PONG`. יוזר כותב תחת ה-prefix של
  ה-ACL שלו ומקבל `NOPERM` מחוץ לו. יוזר עם ACL קריאה בלבד מקבל `NOPERM` על כתיבה.
- **כשל בכל אחד מחמשת הצעדים** (DB גדול מהקלאסטר, ACL לא חוקי, role ויוזר שנוצרו מבחוץ בזמן הריצה, אחרי בדיקת השמות, ACL שנמחק לפני צעד
  ההרשאות): כל ריצה הסתיימה `rolled_back` עם קוד השגיאה של הקלאסטר, ושום דבר לא נשאר בקלאסטר.
- **מקביליות:** שתי בקשות עם אותו שם DB במקביל ⇐ אחת `succeeded`, השנייה `rejected` עם `name_taken`.
- **אותו trace:** בזמן ריצה, אחרי סיום, עם גוף אחר, ושתיים במקביל: בכל המקרים רצה ריצה אחת.
- **קריסה:** השירות נהרג ב-`kill -9` באמצע צעד ה-DB. pod אחר סימן את הפעולה ואת ה-Saga, והנעילה נשארה.
