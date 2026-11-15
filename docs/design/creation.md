# יצירת DB: איך בקשה רצה

מה קורה מרגע ש-`POST /v1/databases/create` מגיע ועד שהתוצאה נשמרת. החוזה עצמו (שדות, קודים): `contracts/service-api.md`.
המנוע, ה-Redis וההתאוששות: `saga-engine-and-state.md`.

**בנוי:** יצירה באתר אחד ויצירת Active-Active (סעיף 6). **לא בנוי:** `planned.md`.

---

## 1. המסלול

![קבלה](../diagrams/12-flow-find-or-start.drawio.svg)

```
POST /v1/databases/create
 ├─ ולידציה של הגוף (Pydantic) ו-traceparent           ⇐ 422 מיד
 ├─ OperationStarter.start_once
 │   ├─ יש פעולה לאותו trace?                           ⇐ 200 עם המצב שלה
 │   ├─ CreationPreparation: שם, קלאסטר, ברירות מחדל     ⇐ 422 / 500 מיד
 │   ├─ התחלה אטומית: running + heartbeat
 │   └─ העברה ל-ThreadPoolTaskRunner                          ⇐ 202
 └─ ברקע: CreationExecution
     ├─ SingleSiteCreationPlanner או ActiveActiveCreationPlanner: תוכנית צעדים
     ├─ SagaExecutor: נעילה ⇐ בדיקת שמות פנויים ⇐ צעדים
     └─ CreationOutcomeTranslator: התוצאה ⇐ OperationStore
```

| רכיב | תיקייה | מה הוא עושה |
|---|---|---|
| `DatabaseCreation` | `creation/` | מה שה-route קורא לו: מעביר ל-`OperationStarter.start_once` את ההכנה, שרצה רק אחרי החיפוש לפי trace |
| `OperationStarter` | `operations/` | הסדר המשותף לכל פקודה: חיפוש לפי trace, הכנה, התחלה אטומית, העברה לרקע (`saga-engine-and-state.md` סעיף 8) |
| `CreationPreparation` | `creation/` | כל מה שאפשר לבדוק בלי הקלאסטר |
| `CreationExecution` | `creation/` | הריצה ברקע, עד רשומת הפעולה הסופית |
| `SingleSiteCreationPlanner` | `planning/` | הבקשה ⇐ תוכנית צעדים ומפתחות נעילה |
| `ActiveActiveCreationPlanner` | `planning/` | בקשת Active-Active ⇐ תוכנית צעדים לכל האתרים ומפתחות נעילה בכל אתר |
| `CreationOutcomeTranslator` | `creation/` | ה-saga record ⇐ הפעולה: עץ ה-DB, או השגיאה ומה שלא בוטל |

![שכבת creation](../diagrams/04-layer-creation.drawio.svg)

![שכבת planning](../diagrams/05-layer-planning.drawio.svg)

**נקודת ההרכבה:** `composition/` (`app_wiring.py`, `cluster_wiring.py`, `state_wiring.py`) בונה את כל המחלקות הקונקרטיות. רק `app` מעליה.

---

## 2. ההכנה (לפני `202`)

![קלאסטר וברירות מחדל](../diagrams/13-flow-cluster-and-defaults.drawio.svg)

1. **שם ה-DB** לפי `config/naming.yaml`. אחרת `invalid_name`.
2. **הקלאסטר** (`SiteClusterResolver`) מתוך `config/clusters.yaml`: רשימה שטוחה, ולכל קלאסטר `name`, `network`,
   `environment`, `site`, `type` ו-`api_url`. ההתאמה היא לפי השדות, ולכן אין היררכיה קבועה בין רשת, סביבה ואתר.
   הקונפיג נדחה בעלייה אם `api_url` חוזר, אם הצירוף של `network`, `environment`, `site` ו-`name` חוזר, או אם קלאסטר
   `dedicated` נקרא `generic`. הבקשה שולחת ב-`cluster` את `generic` או שם של קלאסטר `dedicated`:
   - שם: הקלאסטר מסוג `dedicated` עם אותם רשת, סביבה, אתר ושם.
   - `generic`: כל הקלאסטרים ה-generic באותם רשת, סביבה ואתר הם מועמדים, ו-`ClusterChooser` בוחר. המימוש היום,
     `SingleCandidateChooser`, דורש מועמד אחד בדיוק. כמה ⇐ `configuration_error`. בחירה בין כמה: `planned.md`.
   - אין קלאסטר מתאים ⇐ `no_matching_cluster`.
3. **ברירות מחדל** (`DatabaseDefaults`, `config/database_defaults.yaml`):

   ```yaml
   database_defaults:
     values: {version: "8.4", replication: true, data_persistence: aof, ...}
     persistence_values:
       aof: {aof_policy: appendfsync-every-sec}
       snapshot: {snapshot_policy: [{secs: 3600, writes: 1}]}
     overrides:
       - when: {environment: DEV}
         values: {replication: false}
       - when: {active_active: true}
         values: {eviction_policy: noeviction}
   ```

   - הסדר: `values`, אחריהן כל דריסה שה-`when` שלה מתאים לקלאסטר שנבחר (לפי הסדר ברשימה), ובסוף השדות שהבקשה
     שלחה ולא כ-`null`. התוצאה עוברת ולידציה ב-`NewDatabase`.
   - `when` מתאים לפי כל צירוף של `network`, `environment`, `site`, `type`, `cluster_name` ו-`active_active`.
   - הדריסה היא לפי שדה ברמה העליונה. לשדות של ה-DB אין אובייקטים מקוננים שצריך למזג.
   - **שדות של מצב שמירה:** `aof_policy` שייך ל-`aof` ו-`snapshot_policy` ל-`snapshot`. אחרי המיזוג נקבע
     `data_persistence`. שדות של מצב אחר יוצאים, והשדות של המצב שנבחר מקבלים את `persistence_values` שלו אם הבקשה
     לא שלחה אותם. ב-`disabled` אין אף אחד מהם. בקשה שולחת `aof_policy` או `snapshot_policy` רק יחד עם ה-`data_persistence`
     שלהם, אחרת `422 validation_error`.
   - בעלייה: תווית לא מוכרת, או ערך שלא עובר את `DatabaseOptions`, עוצרים את השירות. כך גם ברירות המחדל שחלות יחד
     על כל קלאסטר בקונפיג: שתי דריסות שכל אחת תקינה לבד ויחד לא, עוצרות את השירות.

4. **ב-Active-Active:** כל אתר עובר את שלבים 2 ו-3 לבד. אחר כך: כל האתרים באותה רשת (אחרת `mixed_networks`), כל אתר
   על קלאסטר אחר (אחרת `duplicate_sites`), קלאסטרים שונים בשם אחר וב-host אחר (אחרת `configuration_error`: הקונפיג
   של הקלאסטרים, לא הבקשה), וכל האתרים יוצאים עם אותן הגדרות (אחרת `configuration_error`, עם שמות השדות השונים).
   סעיף 6.

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
| 5 | `permissions` | `UpdateDatabaseStep` | `PUT /v1/bdbs/{uid}` עם `roles_permissions`: זוג role ↔ ACL לכל יוזר | `PUT` של הרשימה הקודמת |
| 6 | `read-database` | `ReadDatabaseStep` | `GET /v1/bdbs/{uid}`: ה-DB המלא | אין מה לבטל |

- צעדים 2–4 חוזרים לכל יוזר, לפי הסדר בבקשה. צעד 5 אחד לכל היוזרים, ורק כשיש יוזרים. צעד 6 תמיד אחרון.
- **אובייקט מלא:** כל צעד יצירה שומר את כל מה שהקלאסטר החזיר, חוץ מ-`secret_fields` של המשאב (ב-DB:
  `authentication_redis_pass`, `authentication_admin_pass`, `authentication_sasl_pass`), ורק אז בודק שכל שדה שנשלח חזר עם ערך (חוץ מ-
  `unreturned_fields` בקונפיג, היום סיסמת היוזר). חסר ערך ⇐ `incomplete_cluster_object`, כישלון ודאי: ה-uid כבר שמור,
  ולכן הביטול מוחק גם את האובייקט הזה וגם כל מה שנוצר לפניו. אובייקט שנמצא לפי שם (תוצאה לא ידועה) נקרא מלא לפי ה-uid.
- **צעד 6** קורא את ה-DB המלא אחרי שההרשאות עליו. כל שדה של מודל היצירה ו-`database.required_fields` (`uid`, `status`,
  `endpoints`) חייב ערך, וכל endpoint חייב `endpoint_fields` (`dns_name`, `port`, `addr`). בנוסף, `roles_permissions`
  חייב להכיל כל זוג `{role_uid, redis_acl_uid}` שצעד 5 קבע, בלי חשיבות לסדר. אחרת ⇐ אותו כישלון ודאי, והכל מתבטל.
- **כל קריאה לקלאסטר מחזירה את האובייקט המלא:** יצירה, קריאה לפי uid, רשימה (בלי `fields`), מחיקה, עדכון DB, קריאת
  DB, המתנה ל-action (ה-action האחרון) והמתנה ל-DB פעיל (ה-DB האחרון שנקרא). מי שקורא בוחר מה הוא צריך, כך שראוטים
  אחרים משתמשים באותן קריאות בלי קריאה נוספת. צעד עדכון שומר לביטול רק את השדות שהוא משנה.
- **התוצאה** (`service-api.md` סעיף 4) נבנית רק מהאובייקטים ששמורים ב-saga record: ה-DB מצעד 6, היוזר, ה-ACL וה-role
  מתשובות היצירה שלהם. הסיסמה היא זו שהקלאסטר קיבל.
- כל הצעדים הפיכים. אין pivot, ולכן כשל ודאי בכל שלב מחזיר את הקלאסטר למצב שלפני הבקשה.
- ה-role נוצר אחרי ה-DB כי `resources` חייב uid של DB קיים, והיוזר אחרי ה-role כי הוא חייב role.
- ה-uids עוברים בין צעדים דרך ה-`StepResults` (`saga-engine-and-state.md` סעיף 3).
- שמות ה-ACL וה-role וה-`management` מ-`config/user_resources.yaml`.
- ביצירת ACL, role ו-user, אם התשובה כוללת `action_uid`, הצעד מחכה ל-`/v1/actions/{uid}` עד `completed`.
- **המתנה בקלאסטר:** כל המתנה קוראת את המצב כל `poll_interval_seconds` עד `timeout_seconds` (`database.wait`,
  `action.wait`, `crdb.task.wait`), ובודקת פעם אחרונה בדיוק בסוף הזמן. קריאה שנכשלה בשגיאה שבטוח לקרוא אחריה שוב
  (שירות קצה שלא התחבר או לא ענה, 5xx של הקלאסטר, או קוד מ-`cluster_api.transient_error_codes`) נרשמת כ-WARNING,
  והקריאה חוזרת. כל שגיאה אחרת עוצרת את ההמתנה. אם הזמן נגמר ⇐ `cluster_action_timeout`,
  `database_activation_timeout`, `database_deletion_timeout` או `crdb_task_timeout` (בחוזה: `cluster_timeout`). אם אף
  קריאה לא הצליחה עד סוף הזמן, מדווחת שגיאת הקריאה האחרונה במקום ה-timeout, למשל `cluster_unavailable`.
- גוף ה-DB כולל גם `default_user: true`, `authentication_redis_pass` (הסיסמה של `default_user` מ-Secret) ו-`tags`
  (`database.default_tags`). הסיסמה מתווספת רק ברגע השליחה, ולא נכנסת לקלט של הצעד או ל-record.

**שמות.** כל ACL ו-role שייכים ליוזר אחד ב-DB אחד. שם יוזר עם `-` נדחה בולידציה, כי אחרת שתי בקשות שונות יכולות לקבל
אותו שם נגזר (DB `orders` עם יוזר `app-x`, ו-DB `orders-app` עם יוזר `x`).

**נעילה.** מפתחות `{api_url}/database/{db}` ו-`{api_url}/user/{user}` לכל יוזר, לפי כתובת הקלאסטר שנבחר. שמות ה-ACL וה-role נגזרים משם ה-DB, ולכן
הנעילה של ה-DB מכסה אותם.

**בדיקת שמות פנויים** (`CreationNamesCheck`, שמחבר את `NameCheckScope`, `CreationNaming` ו-`NameAvailability`), כ-`check_before_start`: אחרי הנעילה ולפני הצעד הראשון. היא בודקת את ה-DB, ולכל
יוזר את השם שלו ואת שמות ה-ACL וה-role. ל-REST API אין חיפוש לפי שם, ולכן היא שולפת פעם אחת כל סוג משאב (`bdbs`,
`users`, `redis_acls`, `roles`) ומסננת בקוד. היא רצה תחת הנעילה, כי הקלאסטר לא אוכף שם DB ייחודי, ושתי בקשות שבודקות
לפני הנעילה היו עוברות יחד. ההיקף הוא ממשק נפרד (`NameCheckScope`), והמימוש היום (`ChosenClusterScope`)
מחזיר רק את הקלאסטר שנבחר, כך שאפשר להרחיב אותו לקלאסטרים נוספים בלי לשנות את הבדיקה. שם תפוס ⇐ `name_taken`, והנעילה משתחררת.

---

## 4. התוצאה

![ביטול](../diagrams/11-seq-rollback-single-site.drawio.svg)

`CreationExecution` מתרגם כל סוף לרשומת פעולה, ושומר אותה:

| מה קרה | הפעולה |
|---|---|
| ה-Saga הצליח | `succeeded` עם עץ ה-DB (`created_database_result.py`): ה-DB מהקריאה האחרונה, היוזר, ה-ACL וה-role מתשובות היצירה שלהם |
| ה-Saga `rolled_back` או `requires_manual_intervention` | אותו סטטוס, עם `error` של הצעד שעצר (`stopped_at`), ו-`not_rolled_back` |
| שגיאה של הפרויקט לפני שה-Saga התחיל (נעילה, שם תפוס, שגיאת קלאסטר בבדיקת השמות, שגיאה בבניית התוכנית) | `rejected` עם הקוד הציבורי שלה |
| שגיאה (של הפרויקט או לא צפויה) אחרי שה-Saga התחיל | יש record ⇐ כמו בסוף רגיל, מתוך ה-record (record שנשמר כ-`running` ⇐ `requires_manual_intervention`). צעד שנעצר בלי שגיאה משלו מקבל את השגיאה שקטעה את הריצה: שגיאה של הפרויקט עם הקוד וההודעה שלה, או שגיאה לא צפויה כ-`internal_error` עם `unexpected <type>: <text>`. record שלא נקרא ⇐ `requires_manual_intervention` עם אותה שגיאה |
| שגיאה לא צפויה לפני שה-Saga התחיל | אין saga record ⇐ `rejected` עם `internal_error`, וה-`message` הוא `unexpected <type>: <text>` |
| record שאי אפשר לבנות ממנו את התוצאה (למשל uid חסר) | `requires_manual_intervention` עם `internal_error`, וה-`message` הוא `unexpected <type>: <text>`. `not_rolled_back` מופיע כשאפשר לבנות אותו מה-record |

- **`not_rolled_back`** (`CreationOutcomeTranslator`): כל צעד שנשאר `done`, `unresolved`, `compensating` או
  `compensation_failed`, עם הסוג, השם והקלאסטר מהתוכנית, וה-uid מהתוצאה. ב-`permissions` השם וה-uid הם של ה-DB.
  `last_error` הוא `"<code>: <message>"` של השגיאה האחרונה: של הביטול אם נכשל, אחרת של הצעד, עם הקוד הציבורי.
- **קודים ציבוריים** (`PublicErrors`, `config/operation.yaml`): כל קוד פנימי ממופה לקוד מהחוזה. קוד בלי מיפוי ⇐
  `internal_error` ו-WARNING. `cluster_url` ו-`cluster_error_code` נוספים רק לקודים שב-`public_codes_with_cluster_details`.
  לכל קוד ציבורי יש `kind` (`error_kind_by_code`); קוד בלי סוג ⇐ `needs_investigation` ו-WARNING. `Operation.failed`
  נותן ל-`requires_manual_intervention` תמיד `needs_investigation`.
- **סדר השמירה:** המנוע משחרר את הנעילה, ורק אחר כך הפעולה נשמרת.

---

## 5. בדיקות מול קלאסטר אמיתי

הזרימה נבדקה מקצה לקצה מול השירות, cluster-relay וקלאסטר מקומי:
- **הצלחה עם שני יוזרים:** חיבור בלי סיסמה ⇐ `NOAUTH`. `default` עם הסיסמה ⇐ `PONG`. יוזר כותב תחת ה-prefix של
  ה-ACL שלו ומקבל `NOPERM` מחוץ לו. יוזר עם ACL קריאה בלבד מקבל `NOPERM` על כתיבה.
- **כשל בכל אחד מחמשת הצעדים** (DB גדול מהקלאסטר, ACL לא חוקי, role ויוזר שנוצרו מבחוץ בזמן הריצה, אחרי בדיקת השמות, ACL שנמחק לפני צעד
  ההרשאות): כל ריצה הסתיימה `rolled_back` עם קוד השגיאה של הקלאסטר, ושום דבר לא נשאר בקלאסטר.
- **התוצאה:** עץ ה-DB חזר עם ה-endpoint, הפורט וה-addr, כל שדות מודל היצירה כפי שנשמרו, וההרשאה (uids, שם, סיסמה,
  כלל ה-ACL, וה-uid והשם של ה-role). כל ערך הושווה למה שנקרא ישירות מהקלאסטר. כישלון של צעד הקריאה האחרון לא נבדק מול קלאסטר אמיתי: הוא
  מכוסה בטסטים.
- **מקביליות:** שתי בקשות עם אותו שם DB במקביל ⇐ אחת `succeeded`, השנייה `rejected` עם `name_taken`.
- **אותו trace:** בזמן ריצה, אחרי סיום, עם גוף אחר, ושתיים במקביל: בכל המקרים רצה ריצה אחת.
- **קריסה:** השירות נהרג ב-`kill -9` באמצע צעד ה-DB. pod אחר סימן את הפעולה ואת ה-Saga, והנעילה נשארה.

---

## 6. Active-Active

**חוזה:** `active_active: true` עם כמה `sites`. `crdb_guid` הוא ה-guid של ה-CRDB, ו-`clusters[]` כולל ענף לכל קלאסטר.
המפרק הוא `ActiveActiveCreationPlanner`, והצעדים ב-`steps/`: `CreateCrdbStep`, `FindLocalCrdbInstanceStep`,
`UpdateCrdbInstancesStep` ו-`ReadCrdbStep`, ועוד `CreateResourceStep` ו-`ReadDatabaseStep` לכל אתר.

**יצירה:**

![יצירת AA](../diagrams/20-seq-create-active-active.drawio.svg)

| # | צעד | סוג |
|---|---|---|
| 1 | `POST /v1/crdbs` עם `X-Task-ID` ו-`X-Result-TTL` שאנחנו קובעים, המתנה ל-task | הפיך: `DELETE` + task |
| 2 | לכל קלאסטר: איתור ה-bdb המקומי ו-`id` של ה-instance (`GET /v1/crdbs/{guid}` באותו קלאסטר), המתנה ל-`active` | קריאה בלבד |
| 3..N | לכל קלאסטר ולכל יוזר: ACL, role עם `resources` של ה-bdb **המקומי**, user | הפיך |
| N+1 | רק כשיש יוזרים: `PATCH` אחד ל-CRDB עם `instances[].db_config.roles_permissions`, רשימה לכל instance | הפיך: `PATCH` עם הערכים שנקראו לפני השינוי |
| N+2 | לכל קלאסטר: קריאת ה-bdb ובדיקה שההרשאות נשמרו | קריאה בלבד |
| N+3 | קריאת ה-CRDB ובדיקה ש-`default_db_config` מחזיק כל שדה שנשלח (tags משווים לפי `key` ו-`value`) | קריאה בלבד |

- **אותם צעדים, כמה קלאסטרים:** המפרק פורש כל צעד מקומי לצעד לכל קלאסטר, עם מפתח שמתחיל בקלאסטר. אותה מחלקה, פרמטר
  קלאסטר שונה. כשל באחד מבטל את האחרים כרגיל.
- **כל ההגדרות במפורש ב-`default_db_config`:** אותו גוף כמו ביצירה באתר בודד, אחרי מילוי ברירות המחדל. הקלאסטר שומר
  ב-CRDB רק מה שנשלח, ולכן רק כך ה-CRDB מחזיק את התמונה המלאה, ובדיקת drift משווה כל bdb מקומי מולו.
  `instances[].db_config` לא נשלח, חוץ מההרשאות. ברירות מחדל שנותנות ערך שונה לאתרים של אותו CRDB ⇐ שגיאת קונפיג לפני
  ששום דבר נוצר.
- **אותן הגדרות בכל אתר:** כל האתרים מקבלים אותו `default_db_config`, ולכן שדות שחייבים להיות זהים (`version`,
  `sharding`, `shard_key_regex`) לא יכולים להיות שונים.
- **אין dry_run:** יצירה שנכשלת בשלב הבדיקה של הקלאסטר (מקום, פורט, פרטי גישה), גם באתר אחד, לא משאירה כלום באף אתר
  ומחזירה אותה שגיאה שה-dry_run היה מחזיר, ולכן בדיקה מראש לא מוסיפה. אתר שנופל באמצע היצירה הוא מקרה אחר (הסעיף הבא).
- **אתר שנופל באמצע יצירה** (ה-task נשאר `started`): אחרי `crdb.task.wait.timeout_seconds` (600 שניות) ⇐
  `requires_manual_intervention`. לא שולחים cancel (החלטת הבעלים): בניסוי ישן cancel של יצירה עבד ומחק את ה-bdb החלקי, אבל cancel של שינוי מבנה אחר
  (הסרת אתר) השאיר CRDB שאי אפשר למחוק, ולכן לא מסתכנים. אדם מחליט לפי ה-task id ששמור ב-record.
- **task id קבוע:** ה-`X-Task-ID` נגזר מה-saga ומהצעד. בקשה שנשלחת שוב עם אותו id נענית `406 job_exists`, כלומר
  הראשונה הגיעה, והצעד מחכה ל-task הקיים במקום להיכשל. צעד ההרשאות קורא את ה-task שלו לפני שהוא מחליט: task שעוד
  רץ ⇐ תוצאה לא ידועה, וביטול מחכה שה-task יסתיים לפני שהוא משחזר. task שכבר הסתיים ב-`failed` או `canceled` ⇐ כישלון
  ודאי, וה-saga מבטל את מה שנוצר לפניו. גם הקלאסטר חייב להחזיר את אותו id בתשובה, אחרת ⇐
  `requires_manual_intervention`.
- **task id של ביטול:** הביטול (מחיקת ה-CRDB, או שחזור ההרשאות) שולח task id שני, שנגזר מה-id של הצעד
  (`undo_task_id`), כך שב-record יש עד שני task ids לכל צעד. ביטול שנכשל לא נשלח שוב עם id חדש: הוא מצטרף ל-task
  שנכשל עד שהתוצאה פגה, ונגמר בהתערבות ידנית.
- **תוצאה לא ידועה של היצירה:** מאתרים לפי ה-`X-Task-ID` שלנו, לא לפי השם, כי שמות CRDB כפולים מותרים. task שלא
  נמצא (`404`, למשל כי התוצאה שלו פגה) כשקיים CRDB באותו שם ⇐ `requires_manual_intervention`, כי ייתכן שהוא של
  היצירה הזו.
- **בדיקת שמות:** שם ה-DB, היוזרים, ה-ACLs וה-roles פנויים בכל אתר, ושם ה-DB פנוי גם בין ה-CRDBs.
- **רשת:** כל האתרים באותה רשת. אחרת ⇐ `422 mixed_networks`.
- **סביבה מעורבת** לא נבדקת (באחריות השירות שבונה את הבקשות). תוצאה של ההחלטה: אתר DEV ואתר PROD באותה רשת מקבלים
  ברירות מחדל שונות (`replication`), והבקשה נגמרת ב-`500 configuration_error`, למרות שהטעות בבקשה.
- **מספר האתרים** מוגבל רק בקלאסטר: `id` של instance מגיע עד 31. גם אתר אחד (CRDB עם instance אחד) מותר.
- **אתרים כפולים:** שני אתרים על אותו קלאסטר ⇐ `422 duplicate_sites`. שני קלאסטרים שונים עם אותו שם או אותו host ⇐
  `500 configuration_error`: מפתחות הצעדים בנויים משם הקלאסטר, וה-FQDN של ה-instance מה-host.
- **המתאם** הוא הקלאסטר הראשון ברשימה. ה-FQDN (`name` של instance) נלקח מה-URL של הקלאסטר.
- **נעילה:** את ה-DB ואת היוזרים בכל קלאסטר משתתף. `PATCH /v1/crdbs` נשלח בלי `cluster-state-id`, כך שההרשאות
  ב-AA נשענות על הנעילה בלבד, והנעילה מגינה רק מפני הרצות של השירות הזה, לא מפני שינוי מה-UI או מכלי אחר.
  **פתוח:** האם `PATCH /v1/crdbs` מכבד `cluster-state-id` (לא נבדק).
- **תוצאה:** ענף לכל אתר מה-DB המקומי שלו, עם היוזר, ה-ACL וה-role שנוצרו בו. `not_rolled_back` מראה כל משאב באתר שלו,
  ו-CRDB שנשאר עם `crdb_guid`. מפתח של צעד באתר מתחיל בשם הקלאסטר (`c1/acl/app`).
- **בדיקה מול המעבדה (2026-11-14):** יצירה דרך השירות על שני אתרים עם יוזר עברה תוך כ-21 שניות; ACL שנדחה ביטל הכל,
  כולל ה-CRDB, בלי שאריות; שום בקשה או תשובה לא נחסמה בחומת האש.
- **tags:** דרך ה-CRDB (`default_db_config.tags`), לא דרך ה-bdb המקומי.
- **הסנכרון בין האתרים** רץ ישירות בין הקלאסטרים, לא דרך cluster-relay. רק הבקשות של השירות עוברות דרכו. גם
  `api_url` מהקונפיג נשלח כ-URL של ה-instance, והקלאסטר המתאם קורא אליו ישירות, ולכן כל קלאסטר חייב להגיע ל-`api_url`
  של כל האחרים. הסנכרון דורש גם שכל קלאסטר יפענח את `redis-<port>.<fqdn>` של האחרים.
