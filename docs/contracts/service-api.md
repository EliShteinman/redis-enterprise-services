# חוזה: שירות הביניים ⇐ redis-enterprise-services

ה-API ש-redis-enterprise-services חושף לשירות הביניים: מה נשלח לכל route ומה חוזר. אותו חוזה מתואר גם ב-OpenAPI של
השירות (`/docs`), עם תיאור ודוגמה לכל שדה.

**בנוי היום:** יצירת DB באתר אחד ושאילתת סטטוס. **מתוכנן:** סעיף 7.

---

## 1. כללי

| נושא | ערך |
|---|---|
| פורמט | JSON. שדה לא מוכר בגוף הבקשה ⇐ `422 validation_error` |
| מזהה בקשה | header `traceparent` בפורמט W3C, חובה בכל route חוץ מ-`/health`. חסר או לא תקין ⇐ `422 validation_error` על `header.traceparent`. ה-`trace_id` של הפעולה הוא ה-trace id שבו (32 תווי hex) |
| אסינכרוני | פקודה מחזירה מיד `202` עם `trace_id` ו-`status: running`. התוצאה בשאילתת הסטטוס (סעיף 5) |
| IDs | ביצירה לא שולחים IDs. הם חוזרים בתוצאה |
| סיסמאות | נשלחות בבקשה, ולא חוזרות אף פעם |
| הזדהות | אין עדיין (סעיף 7) |

| route | |
|---|---|
| `POST /v1/databases/create` | יצירת DB באתר אחד |
| `GET /v1/operations/{trace_id}` | סטטוס ותוצאה של פעולה |
| `GET /health` | `200 {"status": "ok"}`. בלי `traceparent` |

---

## 2. איך פקודה רצה

![שכבת api](../diagrams/03-layer-api.drawio.svg)

1. **בדיקות מקומיות**, בלי פנייה לקלאסטר: מבנה הגוף, כללי שם ה-DB, ושהיעד מתאים לקלאסטר בקונפיג. כשל ⇐ תשובה
   מיידית עם קוד HTTP (סעיף 6).
2. **קבלה:** `202` עם `{"trace_id", "status": "running"}`. הפעולה רצה ברקע.
3. **תוצאה:** `GET /v1/operations/{trace_id}` עד ש-`status` סופי: `succeeded`, `rejected`, `rolled_back` או
   `requires_manual_intervention`. סטטוס שלא מוכר לקורא אינו סופי.

**אותו trace id פעמיים** לא מתחיל פעולה חדשה, גם עם span id אחר. התשובה היא `200` עם המצב הנוכחי, כמו שאילתת
הסטטוס. לכן כל פקודה צריכה trace משלה.
- רק מבנה הגוף נבדק לפני החיפוש לפי trace. גוף שלא עומד בחוזה ⇐ `422`, גם אם כבר יש פעולה עם אותו trace.
  שאר הבדיקות המקומיות רצות רק כשה-trace חדש.
- פקודה שנדחתה מיד לא נשמרת. אותו trace עם גוף מתוקן מתחיל פעולה חדשה.
- אם השירות לא הצליח להעביר את הפקודה לריצה ברקע (למשל באמצע כיבוי), התשובה `500`, והפעולה נשמרת כ-`rejected`
  עם `internal_error`. אותו trace יקבל `200` עם התוצאה הזו עד שהיא פגה.
- אחרי שהתוצאה פגה (סעיף 5), אותו trace מתחיל פעולה חדשה.

---

## 3. יצירה: `POST /v1/databases/create`

```json
{
  "target": {
    "active_active": false,
    "sites": [
      {"network": "net-a", "site": "dc1", "environment": "PROD", "cluster": {"type": "generic"}}
    ]
  },
  "body": {
    "database": {"name": "orders", "memory_size": 1073741824},
    "users": [
      {"name": "app", "password": "…", "acl": "+@all ~orders:*"}
    ]
  }
}
```

### `target`

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `active_active` | `false` | ✅ | `true` עוד לא נתמך |
| `sites` | list | ✅ | איבר אחד בדיוק |
| `sites[].network` | str | ✅ | |
| `sites[].site` | str | ✅ | |
| `sites[].environment` | `DEV` / `PROD` / `TEST` | ✅ | |
| `sites[].cluster.type` | `dedicated` / `generic` | ✅ | |
| `sites[].cluster.name` | str | רק ב-`dedicated` | אסור ב-`generic` |

**איך נמצא הקלאסטר:** לפי `config/clusters.yaml`, קלאסטר עם אותם `network`, `environment`, `site` ו-`type`, וב-`dedicated`
גם אותו `name`.
- אין קלאסטר מתאים ⇐ `422 unknown_cluster`.
- ב-`generic` צריך להיות בדיוק קלאסטר אחד מתאים. יותר מאחד ⇐ `500 configuration_error`. בחירה בין כמה קלאסטרים
  מתוכננת (סעיף 7).

### `body.database`

| שדה | סוג | חובה |
|---|---|---|
| `name` | str | ✅ |
| `memory_size` | int חיובי (bytes) | ✅ |
| `version` | str | |
| `replication` | bool | |
| `data_persistence` | `disabled` / `aof` / `snapshot` | |
| `aof_policy` | `appendfsync-every-sec` / `appendfsync-always` | |
| `snapshot_policy` | list של `{secs, writes}`, שניהם int חיובי | |
| `sharding` | bool | |
| `shards_count` | int, 1–512 | |
| `shard_key_regex` | list של `{regex}` | |
| `eviction_policy` | אחד מעשרת הערכים של Redis (`noeviction`, `allkeys-lru`, …) | |
| `shards_placement` | `dense` / `sparse` | |
| `proxy_policy` | `single` / `all-master-shards` / `all-nodes` | |
| `slave_ha` | bool | |

**שם ה-DB:** אותיות באנגלית, ספרות ו-`-`, לא מתחיל ולא נגמר ב-`-`, עד 20 תווים (`config/naming.yaml`). אחרת ⇐
`422 invalid_name`, והכללים שהופרו ב-`error.message`.

**ברירות מחדל:** שדה שלא נשלח, או נשלח כ-`null`, מקבל את ברירת המחדל של השירות ליעד (`config/database_defaults.yaml`).
אם אין לשירות ברירת מחדל לשדה, ה-DB נוצר עם ברירת המחדל של Redis. היום:

| שדה | ברירת מחדל |
|---|---|
| `version` | `8.4` |
| `replication` | `true`, וב-`DEV` `false` |
| `data_persistence` | `aof` |
| `aof_policy` | `appendfsync-every-sec` |
| `shards_placement` | `dense` |
| `proxy_policy` | `all-master-shards` |

השירות לא בודק תלות בין שדות (למשל `shard_key_regex` בלי `sharding`). הקלאסטר בודק, וכשהוא דוחה, התוצאה היא
`rolled_back` עם `cluster_request_failed`.

### `body.users[]`

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `users` | list | | ברירת מחדל `[]`. כל שם פעם אחת |
| `users[].name` | str | ✅ | בלי `-` |
| `users[].password` | str | ✅ | לא ריק |
| `users[].acl` | str | ✅ | לא ריק. כלל ACL של Redis, למשל `+@all ~orders:*` |

### מה נוצר בקלאסטר

1. ה-DB, עם הסיסמה של `default_user` מהשירות.
2. לכל יוזר: ACL בשם `{db}-{user}-acl` עם ה-`acl` שלו, role בשם `{db}-{user}-role`, והיוזר עם ה-role.
3. קישור כל role ל-ACL שלו על ה-DB.

לפני שמשהו נוצר, השירות בודק בקלאסטר שכל השמות האלה פנויים: ה-DB, היוזרים, ה-ACLs וה-roles. שם תפוס ⇐ `rejected`
עם `name_taken`.

**אם צעד נכשל בוודאות,** כל מה שכבר נוצר נמחק בסדר הפוך, וההרשאות על ה-DB חוזרות לערכים הקודמים. התוצאה
`rolled_back`.

**אם לא ידוע אם צעד בוצע** (למשל timeout מול הקלאסטר), השירות בודק בקלאסטר. אם הוא לא יכול לקבוע מה קרה, הוא לא
מבטל כלום, והתוצאה `requires_manual_intervention`. כך גם כשביטול נכשל.

---

## 4. התשובה

![מודלי ה-API](../diagrams/19-api-models-create.drawio.svg)

### קבלה (`202`)

```json
{"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "status": "running"}
```

### הצלחה

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "succeeded",
  "database": {
    "name": "orders",
    "active_active": false,
    "db_id": 7,
    "clusters": [
      {
        "url": "https://cluster-a.net-a:9443",
        "network": "net-a", "site": "dc1", "environment": "PROD",
        "db_uid": 7,
        "users": [ {"name": "app", "user_uid": 12, "role_uid": 4, "acl_uid": 9} ]
      }
    ]
  }
}
```

| שדה | הערה |
|---|---|
| `database.db_id` | ה-uid של ה-DB בקלאסטר |
| `database.clusters[]` | קלאסטר אחד |
| `database.clusters[].url` | כתובת ה-API של הקלאסטר |
| `database.clusters[].users[]` | היוזרים, עם ה-uids של היוזר, ה-role וה-ACL |

### כישלון

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "rolled_back",
  "database": null,
  "error": {
    "code": "cluster_request_failed",
    "message": "…",
    "cluster": "https://cluster-a.net-a:9443",
    "cluster_error_code": "invalid_schema"
  },
  "not_rolled_back": []
}
```

| `status` | משמעות |
|---|---|
| `running` | הפעולה עוד רצה |
| `succeeded` | הכל הצליח |
| `rejected` | נדחה לפני ששום דבר השתנה. הסיבה ב-`error.code` |
| `rolled_back` | נכשל, והכל בוטל. שום דבר לא השתנה |
| `requires_manual_intervention` | נכשל, ולא הכל בוטל, או שלא ידוע מה נשאר. דורש טיפול ידני |

**`error`:** השגיאה של הצעד שעצר את הפעולה. `cluster` ו-`cluster_error_code` מופיעים רק ב-`cluster_request_failed`,
`cluster_unavailable` ו-`cluster_timeout`. `cluster_error_code` מופיע רק כשהקלאסטר החזיר קוד שגיאה משלו.

**`not_rolled_back[]`:** מה שנשאר בקלאסטר.
- ב-`rolled_back`: רשימה ריקה.
- ב-`requires_manual_intervention`: מה שנשאר, כולל משאב שלא ידוע אם נוצר (`uid: null`, והשגיאה של הצעד). השדה
  לא מופיע אחרי קריסה שהסריקה זיהתה (הסריקה לא בונה אותו), או כשה-record של הריצה לא נקרא. בשני המקרים הקוד
  `internal_error`.
- ב-`rejected`: לא מופיע.

| שדה | הערה |
|---|---|
| `cluster` | כתובת הקלאסטר |
| `type` | `database`, `acl`, `role`, `user` או `permissions` (הקישור של roles ל-ACLs על ה-DB) |
| `name` | שם המשאב. ב-`permissions`: שם ה-DB |
| `uid` | ה-uid בקלאסטר, או `null` כשלא ידוע אם המשאב נוצר. ב-`permissions`: ה-uid של ה-DB |
| `error` | `"<code>: <message>"` של השגיאה האחרונה (של הביטול אם נכשל, אחרת של הצעד), או `null` |

---

## 5. סטטוס: `GET /v1/operations/{trace_id}`

`200` עם המצב הנוכחי (סעיף 4). `trace_id` לא מוכר ⇐ `404 operation_not_found`.

**כמה זמן התוצאה נשמרת:** `succeeded`, `rejected` ו-`rolled_back` נשמרים 7 ימים (`state.finished_operation_ttl_seconds`),
ואחר כך ה-`trace_id` לא מוכר. `requires_manual_intervention` נשמר עד שמטפלים בו ידנית.

**קריסה:** אם ה-pod שהריץ פעולה נפל, pod אחר מזהה את זה תוך כדקה או שתיים ומסמן אותה:
- `rejected` עם `internal_error`, אם הריצה עוד לא התחילה (לא נוצר כלום);
- `rolled_back` עם `internal_error`, אם הריצה כבר הסתיימה בביטול מלא ורק שמירת הפעולה אבדה;
- אחרת `requires_manual_intervention` עם `internal_error`, גם אם בפועל עוד לא נוצר כלום.

**נעילה אחרי `requires_manual_intervention`:** בדרך כלל הנעילה על ה-DB ועל היוזרים נשארת, גם אחרי קריסה. עד שמטפלים
בפעולה ידנית, כל פקודה על אותם שמות באותו קלאסטר מסתיימת ב-`resources_locked`. יוצא מן הכלל: Saga שהסתיימה
(`succeeded` או `rolled_back`) בלי שה-record הסופי שלה נכתב כבר שחררה את הנעילה. הפעולה מסומנת
`requires_manual_intervention`, אבל פקודות חדשות על אותם שמות לא נחסמות.

---

## 6. שגיאות

תשובה מיידית עם שגיאה בנויה כמו כישלון בסטטוס: `{"trace_id", "status": "rejected", "database": null, "error"}`.
ב-`validation_error` יש גם `error.details`: רשימה של `{field, message}` לכל שדה שלא עומד בחוזה, למשל
`body.body.database.memory_size` או `header.traceparent`.

| `code` | איפה | מתי |
|---|---|---|
| `validation_error` | מיד, `422` | הבקשה לא עומדת בחוזה |
| `invalid_name` | מיד, `422` | שם ה-DB לא עומד בכללי השמות |
| `unknown_cluster` | מיד, `422` | אין קלאסטר שמתאים ליעד |
| `not_found` | מיד, `404` | כתובת לא קיימת |
| `operation_not_found` | מיד, `404` | `trace_id` לא מוכר, או שהתוצאה שלו כבר פגה |
| `method_not_allowed` | מיד, `405` | method שהכתובת לא מקבלת |
| `configuration_error` | מיד, `500` | בעיה בקונפיג של השירות, למשל כמה קלאסטרים `generic` לאותו יעד |
| `internal_error` | מיד `500`, או בסטטוס | שגיאה לא צפויה (`message` קבוע: `internal error`), או שגיאה פנימית בלי קוד ציבורי משלה (התיאור שלה ב-`message`). הפרטים בלוג לפי `trace_id` |
| `name_taken` | בסטטוס, `rejected` | שם של DB, יוזר, ACL או role תפוס בקלאסטר |
| `resources_locked` | בסטטוס, `rejected` | פעולה אחרת על אותו DB או אותם יוזרים, באותו קלאסטר, לא הסתיימה תוך 30 שניות |
| `cluster_request_failed` | בסטטוס | הקלאסטר דחה בקשה, DB הגיע ל-`creation-failed`, או פעולה בקלאסטר הסתיימה ב-`failed`, `cancelled` או `aborted` |
| `cluster_unavailable` | בסטטוס | הקלאסטר או שירות הקצה לא זמינים, או שהתשובה לא קריאה |
| `cluster_timeout` | בסטטוס | הקלאסטר לא סיים פעולה בזמן, למשל DB שלא הגיע ל-`active` |

אלה הקודים היחידים שחוזרים. שגיאה פנימית אחרת חוזרת כ-`internal_error`. המיפוי מהקודים הפנימיים ב-
`config/operation.yaml`.

---

## 7. מתוכנן

לא בנוי עדיין. העיצוב ב-`docs/design/planned.md`.

| נושא | מה ישתנה בחוזה |
|---|---|
| בחירת קלאסטר | ב-`generic` השירות יבחר קלאסטר שיש בו מקום מבין כמה. קוד חדש `insufficient_resources` |
| הזדהות | `Authorization` בכל route, אחרת `401 unauthenticated` |
| Active-Active | `active_active: true` עם כמה `sites`. `db_id` יהיה UUID, ו-`clusters[]` יכיל אתר לכל קלאסטר. סטטוס חדש, `pending_cleanup`, כשהיצירה נקטעה וניקוי האתרים עוד רץ. הוא לא סופי |
| עריכה ומחיקה: היעד | `target: {active_active, db_id, clusters}`, מהתוצאה של היצירה, שונה מה-`target` של יצירה |
| עריכה ומחיקה: קודים | `database_not_found`, `clusters_mismatch`, `sites_diverged` בסטטוס (`rejected`) |
| עריכת DB | `POST /v1/databases/update` |
| עריכת יוזרים | `POST /v1/databases/users`, עם רשימת היוזרים המלאה. סיסמה חסרה או מיותרת ⇐ `422 password_rules` |
| מחיקה | `POST /v1/databases/delete` |
| קריאה ישירה לקלאסטר | `POST /v1/cluster-requests`, בלי rollback |
