# ה-REST API של Redis Enterprise: מה העיצוב נשען עליו

התנהגויות של [Redis Software REST API](https://redis.io/docs/latest/operate/rs/references/rest-api/) שהתיעוד לא עונה
עליהן, או שהעיצוב תלוי בהן. כולן נבדקו מול Redis Enterprise 8.x בקלאסטרים המקומיים (`docker/`), רובן גם דרך
cluster-relay. מה בנוי ומה מתוכנן: `creation.md`, `planned.md`.

---

## 1. איתור לפי שם

ל-API אין חיפוש לפי שם. מאתרים משאב בשליפה של כל הרשימה מאותו סוג וסינון בקוד. כך עובדים אחרי תוצאה לא ידועה,
ובבדיקת השמות הפנויים (פעם אחת לכל סוג, לא פעם לכל שם).

| משאב | שם ייחודי? | שליפה |
|---|---|---|
| ACL | כן. שם קיים ⇐ `409 name_already_exists`, תלוי רישיות | `GET /v1/redis_acls` |
| role | כן, כמו ACL | `GET /v1/roles` |
| user | כן, כמו ACL. גם בלי `email` | `GET /v1/users`. `fields` לא מצמצם, וחוזר הכל |
| DB | **לא.** ה-API מקבל שני DBs עם אותו שם (ה-UI לא) | `GET /v1/bdbs?fields=uid,name` |
| CRDB | לפי `X-Task-ID` שאנחנו קובעים | `GET /v1/crdb_tasks/{id}` מחזיר את `crdb_guid` |

## 2. פעולות אסינכרוניות

| פעולה | איך יודעים שהסתיימה |
|---|---|
| יצירה ועדכון של DB | `status` חוזר ל-`active` (בדרך: `pending`, `active-change-pending`). התשובה כוללת `action_uid`. 1–6 שניות |
| מחיקת DB | `delete-pending`, ואז `404`. כשנייה עד 4 שניות |
| ACL, role, user | אם יש `action_uid`, `GET /v1/actions/{uid}` עד `completed` (או `failed`, `cancelled`, `aborted`) |
| CRDB | `GET /v1/crdb_tasks/{id}` עד `finished` או `failed`. ב-`failed`: `errors` עם `cluster_name` |

בלי ההמתנה הצעד הבא נדחה: `PUT` ל-bdb מיד אחרי מחיקת role נדחה ב-`409 busy`, ו-`PUT` בזמן `active-change-pending`
נדחה ב-`409 db_busy`. שניהם זמניים.

## 3. משאבים

### ACL

- יצירה: `POST /v1/redis_acls` `{name, acl}`. התשובה ה-ACL המלא, בלי `action_uid`. כלל שגוי ⇐ `400 invalid_param` עם
  השגיאה של Redis. כלל ריק ⇐ `400 missing_field`.
- מחיקה: `action_uid`, וה-ACL נעלם מיד (`404 redis_acl_not_exist`).
- **יצירה מחדש עם אותו `uid` עובדת.**
- מחיקה של ACL שמחובר ל-DB מצליחה, והקלאסטר מסיר בעצמו את הזוגות שלו מ-`roles_permissions`.
- ACLs מובנים (`Full Access`) read-only: עריכה או מחיקה ⇐ `409`.

### role

- יצירה: `POST /v1/roles` `{name, management, resources: [{type: db, uids: ["7"]}]}`. ה-uids כמחרוזות; מספר ⇐
  `400 invalid_schema`. DB שלא קיים ⇐ `404 db_not_found`. `management` לא מוכר ⇐ `400` עם הערכים המותרים. התשובה בלי
  `action_uid`.
- מחיקה: `action_uid` (כחצי שנייה), וה-role נעלם מיד.
- **יצירה מחדש עם אותו `uid` עובדת.**
- `resources` מגביל את הגישה הניהולית (UI ו-REST) ל-DBs מסוימים. `uids: []` = אף DB. שדה חסר = כל ה-DBs. מחיקת DB
  מסירה אותו מ-`resources`.
- role שיוזר משתמש בו לא נמחק: `406 role_in_use`. מחיקה של role שמחובר ל-DB מסירה את הזוגות שלו, כמו ב-ACL.
- יוזר עם `management: none` מקבל `403` מה-REST API.

### user

- יצירה: `POST /v1/users` `{name, password, role_uids}`. התשובה היוזר המלא עם `action_uid`, והיוזר קיים מיד. role שלא
  קיים ⇐ `404 role_not_exist`. יוזר בלי role ⇐ `400`. סיסמה חלשה מתקבלת. `auth_method` ברירת מחדל `regular`.
- מחיקה: `action_uid`, והיוזר נעלם מיד (`404 user_not_exist`).
- **`uid` לא נשמר ביצירה מחדש:** `POST` מתעלם ממנו בשקט. אף משאב לא מפנה ל-uid של יוזר, ולכן זה לא שובר הפניות.
- **סיסמאות לא חוזרות מה-API.** `/v1/users/password` מאפשר כמה סיסמאות ליוזר (הוספה, החלפה, מחיקה).
- `email_alerts` דלוק כברירת מחדל ביוזר חדש.

### DB (bdb)

- יצירה: `POST /v1/bdbs` מחזיר את ה-bdb המלא עם `uid`, `status: pending` ו-`action_uid`.
- **התשובות ליצירה, ל-`GET` המלא ולמחיקה כוללות `authentication_redis_pass`, `authentication_admin_pass` ו-
  `authentication_sasl_pass` בטקסט גלוי.** לכן תוצאה של צעד היא רק `uid`, `name` ו-`action_uid`, ו-snapshot מבקש רק
  שדות מסוימים.
- `default_user: true` עם `authentication_redis_pass` ⇐ חיבור בלי סיסמה נדחה (`NOAUTH`), ועם הסיסמה עובד. בלי
  סיסמה, כל אחד מתחבר.
- `GET /v1/bdbs/{uid}?fields=a,b` מחזיר רק את השדות. שם שדה לא קיים ⇐ `406 invalid_fields_query_param`. שדה קיים שלא
  הוגדר ב-DB (למשל `tags` לפני שהוגדר) לא חוזר בכלל, ולכן אין לו snapshot.
- `PUT` עם שדות בודדים ⇐ `200` וה-bdb המלא, `active-change-pending`. גם `PUT` עם אותו ערך עובר ל-`active-change-pending`.
  שדה לא קיים ⇐ `400 invalid_schema`. `PUT` עם `uid` ⇐ `500`.
- `tags`: הקלאסטר מוסיף לכל tag `isSystem: false`. `[]` מנקה. `null` ⇐ `400 invalid_schema`.
- בגרסה 8.x כל DB נוצר עם `bf`, `ReJSON`, `timeseries` ו-`search`.
- **`data_persistence: snapshot` חייב `snapshot_policy`.** בלי מדיניות ⇐ `406 invalid_data_persistence` ("Snapshot policy is
  missing"). `aof_policy` שנשלח עם `snapshot` נשמר בלי שימוש. נבדק ב-2026-11-09.
- **לא קובעים `uid` ביצירה.** לפי התיעוד, מי שקובע uid חייב לקבוע אותו בכל ה-DBs שאחריו, כי המספור האוטומטי עלול
  להתנגש בו.

**הפיכות של שדות** (על DB עם נתונים):

| שינוי | תוצאה | הפיך |
|---|---|---|
| `memory_size` למעלה ולמטה, `eviction_policy`, `data_persistence` | הצליח, הנתונים נשמרו | ✅ |
| הפעלת `sharding` (shard אחד) | הצליח | ✅ |
| `replication` הפעלה וכיבוי (2 nodes) | הצליח בשני הכיוונים, כ-2 שניות | ✅ |
| `shards_count` 1 ⇐ 2 | הצליח | ⛔ ההחזרה נכשלת |
| `shards_count` 2 ⇐ 1 | `406` ("requires asm_scaling") | - |
| כיבוי `sharding` עם 2 shards | `406 invalid_sharding` | - |
| `replication` עם node אחד | `406` | - |

### הרשאות (`roles_permissions`)

רשימה בתוך ה-bdb: `[{role_uid, redis_acl_uid}]`. `PUT` שולח את הרשימה המלאה ומחליף את הקודמת.

ההחזרה של ה-snapshot בביטול בטוחה כי לפי החוזה הרשאות לא נערכות יחד עם שינויים אחרים ב-DB, והנעילה מונעת ריצה
אחרת של השירות. שינוי מבחוץ (ה-UI של Redis) בין ה-`PUT` שלנו לביטול לא נדרס: אם ה-DB לא מחזיק לא את הערכים
הישנים ולא את החדשים, הביטול נעצר ב-`UpdateOutcomeUnclearError` (התערבות ידנית), ושינוי בשדה אחר מכשיל את ה-`PUT`
המותנה ב-`wrong_cluster_state_id`.

### dry_run

- קיים ביצירה ובעריכה של `bdbs`, `users`, `roles`, `redis_acls` ו-`crdbs`, ולא יוצר כלום.
- ב-`bdbs`: `POST /v1/bdbs?dry_run=1`. יש מקום ⇐ `200`. אין זיכרון ⇐ `406 insufficient_resources`. חריגה מה-shards
  של הרישיון ⇐ `400 invalid_license`.
- `provisional_memory` מ-`GET /v1/cluster/stats/last` (הזיכרון שעוד אפשר להקצות) תואם אותו: 7.52GB פנויים, dry_run
  עבר ב-1GB ונכשל ב-8GB.
- צעד שתלוי בתוצאה של צעד קודם (למשל יוזר עם `role_uids` של role שעוד לא נוצר) לא ניתן לבדיקה מראש.

### CRDB

- הבקשה ליצירה כוללת לכל קלאסטר URL, FQDN (`name`) ופרטי גישה. התשובה כוללת סיסמאות לכל instance.
- `X-Task-ID` חייב להיות UUID תקני (גרסאות 1–5); ערך אחר ⇐ `400`. אותו `X-Task-ID` פעמיים ⇐ `406 job_exists`, ולא
  נוצר CRDB שני. תוצאת task נשמרת 500 שניות כברירת מחדל, ולכן שולחים `X-Result-TTL` ארוך יותר. אם ה-task כבר לא
  שמור, מאתרים לפי שם ב-`GET /v1/crdbs`.
- את ה-`guid` הקלאסטר מייצר. אפשר לקבוע אותו ביצירה, אבל לא משתמשים בזה.
- dry_run: `dry_run=true` בלבד (`dry_run=1` נדחה). התשובה תמיד `200` עם task `queued`, והתוצאה רק ב-task. הוא בודק
  בכל אתר מקום, פורט ופרטי גישה. כשכמה אתרים בעייתיים, מדווח רק הראשון.
- יצירה שנכשלת באתר אחד (בשלב הבדיקה) לא משאירה כלום באף אתר.
- אתר שנופל באמצע יצירה: ה-task נשאר `started` בלי הגבלה, באתרים התקינים כבר יש bdb מקומי, וה-CRDB לא מופיע ב-
  `GET /v1/crdbs`. `POST /v1/crdb_tasks/{id}/actions/cancel` נכנס לתוקף כשהאתר חוזר, וה-bdb החלקי נמחק. בלי cancel
  היצירה מסתיימת. לא משתמשים ב-`force`, כי הוא עלול לשבור את ה-CRDB.
- מחיקה: `DELETE /v1/crdbs/{guid}` עם task. כ-10 שניות.
- `GET /v1/crdbs` מחזיר `{"crdbs": [...]}`.
- ה-uid של ה-bdb המקומי ידוע רק לקלאסטר עצמו: `local_databases` או `instances[].db_uid` של `GET /v1/crdbs/{guid}`
  באותו קלאסטר. לכן שואלים כל קלאסטר בנפרד. ה-`id` של כל instance ושם הקלאסטר שלו ב-`instances`.
- `instances[].db_config` דורס את `default_db_config` רק באותו קלאסטר. `PATCH` ל-`default_db_config` לא דורס override כזה.
- `PATCH` עם `instances: [{id, db_config: {roles_permissions}}]` מעדכן כל bdb מקומי עם הזוגות שלו (כ-7 שניות),
  וה-CRDB שומר אותם. `[]` בכל instance מחזיר את שניהם לרשימה ריקה. התיעוד לא מזכיר את השדה ב-`db_config`.
- `tags` דרך `default_db_config` מגיעים לכל הקלאסטרים. `PUT` ל-bdb מקומי נשאר רק בו.
- ה-CRDB נוצר עם `search` ו-`ReJSON` בלבד.

## 4. עדכון מותנה (`cluster-state-id`)

כל תשובה כוללת header `cluster-state-id`. `PUT /v1/bdbs/{uid}` עם המזהה, אחרי שהמצב השתנה ⇐ `409 wrong_cluster_state_id`,
והשינוי של האחר נשמר.

| מה השתנה בינתיים | `PUT` עם המזהה הישן |
|---|---|
| `roles_permissions` של אותו DB | נדחה |
| DB **אחר** | נדחה: המזהה של כל הקלאסטר |
| יצירת ACL | עובר |
| DB שעבר מ-pending ל-`active` | נדחה: המזהה עולה גם בלי שינוי שלנו |

לכן לוקחים את המזהה מה-`GET` שממש לפני ה-`PUT`, ו-`wrong_cluster_state_id` הוא שגיאה זמנית. לא נבדק על `PATCH /v1/crdbs`.

## 5. ריצות במקביל

`roles_permissions` הוא רשימה אחת, ושינוי שלה הוא קריאה ואז כתיבה. שתי ריצות במקביל דורסות זו את זו:

| זמן | ריצה A | ריצה B | ב-DB |
|---|---|---|---|
| 1 | `GET` ⇐ `[X]` | | `[X]` |
| 2 | | `GET` ⇐ `[X]` | `[X]` |
| 3 | `PUT [X, A]` | | `[X, A]` |
| 4 | | `PUT [X, B]` | `[X, B]`: A נעלם |

לכן השירות נועל את ה-DB לכל משך הריצה, ושולח `cluster-state-id`. שינוי מחוץ לשירות (ה-UI של Redis) נתפס רק על ידי
`cluster-state-id`.
