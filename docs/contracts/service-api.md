# חוזה: שירות הביניים ⇐ redis-enterprise-services

**סטטוס:** טיוטה
**תאריך:** 2026-10-25

המסמך מגדיר את ה-API ש-redis-enterprise-services חושף: מה נשלח לכל route, ומה חוזר. שירות הביניים נבנה לפיו.

---

## 1. כללי

| נושא | ערך |
|---|---|
| פורמט | JSON |
| מזהה בקשה | header `traceparent`, חובה בכל בקשה. בקשה חוזרת עם אותו trace מקבלת את אותה תשובה |
| הזדהות | חובה בכל route: שם משתמש וסיסמה, `Authorization: Basic`. אחרת `401 unauthenticated` |
| אסינכרוני | פקודה מחזירה מיד `202` עם `trace_id` ו-`status: running`. התוצאה הסופית בשאילתת הסטטוס (סעיף 9) |
| IDs | ביצירה לא שולחים IDs. הם חוזרים בתוצאה (שאילתת הסטטוס), ונשלחים בבקשות הבאות |
| סיסמאות | נשלחות בבקשה, ולא חוזרות אף פעם |

---

## 2. Routes

כל פקודה (יצירה, עריכה, מחיקה) עובדת כך:

1. **בדיקות מקומיות**, בלי פנייה לקלאסטר: הזדהות, ולידציה, כללי סיסמה, והאם היעד או הכתובות בקונפיג. כשל ⇐
   תשובה מיידית עם קוד HTTP (סעיף 8).
2. **קבלה:** `202` עם `{"trace_id", "status": "running"}`. הפעולה רצה ברקע.
3. **תוצאה:** `GET /v1/operations/{trace_id}` עד ש-`status` שונה מ-`running`.

פקודה חוזרת עם אותו `traceparent` לא מתחילה פעולה חדשה. היא מחזירה מיד את המצב הנוכחי, כמו שאילתת הסטטוס.

| פעולה | route |
|---|---|
| יצירה | `POST /v1/databases/create` |
| עריכת DB | `POST /v1/databases/update` |
| עריכת יוזרים | `POST /v1/databases/users` |
| מחיקה | `POST /v1/databases/delete` |
| סטטוס | `GET /v1/operations/{trace_id}` |
| קריאה ישירה לקלאסטר | `POST /v1/cluster-requests` |

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

| שדה | סוג | חובה | ברירת מחדל | הערה |
|---|---|---|---|---|
| `active_active` | bool | ✅ | | |
| `sites` | list | ✅ | | איבר אחד באתר בודד, שניים או יותר ב-AA |
| `sites[].network` | str | ✅ | | |
| `sites[].site` | str | ✅ | | |
| `sites[].environment` | `DEV` / `PROD` / `TEST` | ✅ | | |
| `sites[].cluster.type` | `dedicated` / `generic` | ✅ | | `generic`: השירות בוחר קלאסטר |
| `sites[].cluster.name` | str | רק ב-`dedicated` | | |

### `body.database`

| שדה | סוג | חובה | ברירת מחדל |
|---|---|---|---|
| `name` | str | ✅ | |
| `memory_size` | int (bytes) | ✅ | |
| `version` | str | | `8.4` |
| `data_persistence` | `disabled` / `aof` / `snapshot` | | `aof` |
| `aof_policy` | `appendfsync-every-sec` / `appendfsync-always` | | `appendfsync-every-sec` |
| `snapshot_policy` | list | | רק כש-`data_persistence` הוא `snapshot` |
| `replication` | bool | | `true`, וב-DEV `false` |
| `sharding` | bool | | |
| `shards_count` | int | | |
| `shard_key_regex` | list | | רק כש-`sharding` הוא `true` |
| `eviction_policy` | str | | |
| `shards_placement` | `dense` / `sparse` | | `dense` |
| `proxy_policy` | str | | `all-master-shards` |
| `slave_ha` | bool | | |

שדה בלי ערך בעמודת ברירת המחדל הוא אופציונלי. אם לא נשלח, ה-DB נוצר עם ברירת המחדל של Redis. שדה שנשלח כ-`null` נחשב כאילו לא נשלח.

### `body.users[]`

| שדה | סוג | חובה | ברירת מחדל |
|---|---|---|---|
| `users` | list | | `[]` |
| `users[].name` | str | ✅ | |
| `users[].password` | str | ✅ | |
| `users[].acl` | str | ✅ | |

`acl` הוא מחרוזת ACL של Redis, למשל `+@all ~orders:*`.

### תשובה

`202`. בסיום: עץ ה-DB בשאילתת הסטטוס (סעיף 8).

---

## 4. `target` של עריכה ומחיקה

כל הבקשות בסעיפים 5–7 מקבלות את אותו `target`, עם הערכים שחזרו בתוצאה של היצירה:

```json
"target": {
  "active_active": true,
  "db_id": "b89590d5-b17f-4047-b9c0-debeaa6a744c",
  "clusters": ["https://cluster-a.net-a:9443", "https://cluster-b.net-b:9443"]
}
```

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `active_active` | bool | ✅ | |
| `db_id` | int או UUID | ✅ | int באתר בודד, UUID ב-AA. `database.db_id` מהתשובה |
| `clusters` | list of URL | ✅ | `database.clusters[].url` מהתשובה. ב-AA כל האתרים |

---

## 5. עריכת DB: `POST /v1/databases/update`

```json
{
  "target": { … },
  "body": {"memory_size": 2147483648, "eviction_policy": "volatile-lru"}
}
```

- `body`: כל שדה מ-`body.database` של היצירה (סעיף 3), חוץ מ-`name`. לפחות שדה אחד.
- רק השדות שנשלחו משתנים. ברירות מחדל לא מוחלות.

תשובה: `202`. בסיום: עץ ה-DB בשאילתת הסטטוס.

---

## 6. עריכת יוזרים: `POST /v1/databases/users`

```json
{
  "target": { … },
  "body": {
    "users": [
      {"name": "app", "acl": "+@all ~orders:*"},
      {"name": "reporter", "acl": "+@read ~*", "password": "…", "old_password": "…"},
      {"name": "etl", "acl": "+@all ~*", "password": "…"}
    ]
  }
}
```

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `users` | list | ✅ | **הרשימה המלאה אחרי העריכה.** יוזר שלא ברשימה נמחק |
| `users[].name` | str | ✅ | |
| `users[].acl` | str | ✅ | |
| `users[].password` | str | ראו טבלה | |
| `users[].old_password` | str | ראו טבלה | |

| יוזר | `password` | `old_password` |
|---|---|---|
| חדש | חובה | לא נשלח |
| קיים, הסיסמה לא משתנה | לא נשלח | לא נשלח |
| קיים, הסיסמה משתנה | חובה | חובה |

שינוי שם של יוזר הוא מחיקה של הישן והוספה של חדש.

תשובה: `202`. בסיום: עץ ה-DB בשאילתת הסטטוס.

---

## 7. מחיקה: `POST /v1/databases/delete`

```json
{ "target": { … } }
```

תשובה: `202`. בסיום: `status: succeeded` ו-`database: null` בשאילתת הסטטוס.

---

## 8. התשובה

### קבלה (`202`)

```json
{"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "status": "running"}
```

### תוצאה: הצלחה

שאילתת הסטטוס מחזירה `200` עם:

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "succeeded",
  "database": {
    "name": "orders",
    "active_active": true,
    "db_id": "b89590d5-b17f-4047-b9c0-debeaa6a744c",
    "clusters": [
      {
        "url": "https://cluster-a.net-a:9443",
        "network": "net-a", "site": "dc1", "environment": "PROD",
        "db_uid": 7,
        "users": [ {"name": "app", "user_uid": 12, "role_uid": 4, "acl_uid": 9} ]
      },
      {
        "url": "https://cluster-b.net-b:9443",
        "network": "net-b", "site": "dc2", "environment": "PROD",
        "db_uid": 3,
        "users": [ {"name": "app", "user_uid": 20, "role_uid": 6, "acl_uid": 2} ]
      }
    ]
  }
}
```

| שדה | הערה |
|---|---|
| `database.db_id` | int באתר בודד, UUID ב-AA. נשלח ב-`target.db_id` בבקשות הבאות |
| `database.clusters[]` | אחד לכל אתר. באתר בודד יש אחד |
| `database.clusters[].url` | נשלח ב-`target.clusters` בבקשות הבאות |
| `database.clusters[].db_uid` | ה-uid של ה-DB באותו קלאסטר |
| `database.clusters[].users[]` | היוזרים באותו קלאסטר, עם ה-uids שלהם שם |

### תוצאה: כישלון

שאילתת הסטטוס מחזירה `200` עם:

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "rolled_back",
  "database": null,
  "error": {
    "code": "step_rejected",
    "message": "…",
    "cluster": "https://cluster-b.net-b:9443",
    "cluster_error_code": "insufficient_resources"
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
| `requires_manual_intervention` | נכשל, ולא הכל בוטל. `not_rolled_back` מפרט מה נשאר |
| `pending_cleanup` | timeout ביצירת AA. נשלח ביטול, והשאילתה הבאה תראה אם הוא הסתיים |

`not_rolled_back[]`: `cluster`, `type`, `name`, `uid`, `error`.

### `error.code`

| `code` | איפה | מתי |
|---|---|---|
| `unauthenticated` | מיד, `401` | |
| `validation_error` | מיד, `422` | הבקשה לא עומדת בחוזה. `error.details` לכל שדה |
| `password_rules` | מיד, `422` | הפרה של טבלת הסיסמאות (סעיף 6) |
| `unknown_cluster` | מיד, `422` | כתובת או יעד לא מוכרים |
| `configuration_error` | מיד, `500` | בעיה בקונפיג של השירות |
| `internal_error` | מיד, `500` | שגיאה לא צפויה בשירות. הפרטים בלוג, לפי `trace_id` |
| `not_found` | מיד, `404` | כתובת לא קיימת |
| `method_not_allowed` | מיד, `405` | method שהכתובת לא מקבלת |
| `database_not_found` | בסטטוס, `rejected` | `db_id` לא נמצא |
| `clusters_mismatch` | בסטטוס, `rejected` | `clusters` לא תואם לאתרים של ה-DB |
| `sites_diverged` | בסטטוס, `rejected` | ב-AA, אתר שונה מהאחרים בשדה שבעריכה |
| `name_taken` | בסטטוס, `rejected` | שם DB או יוזר תפוס |
| `insufficient_resources` | בסטטוס, `rejected` | אין מקום באף קלאסטר מתאים |
| `database_locked` | בסטטוס, `rejected` | פעולה אחרת רצה על ה-DB, ולא הסתיימה בזמן |
| `step_rejected` | בסטטוס, `rolled_back` | הקלאסטר דחה צעד. הקוד שלו ב-`error.cluster_error_code` |
| `cluster_unavailable` | בסטטוס, `rolled_back` | הקלאסטר או שירות הקצה לא זמינים |

תשובה מיידית עם שגיאה בנויה כמו כישלון בסטטוס: `{"trace_id", "status": "rejected", "database": null, "error"}`.

---

## 9. סטטוס: `GET /v1/operations/{trace_id}`

`200` עם המצב הנוכחי (סעיף 8). בזמן ריצה `status` הוא `running`. `trace_id` לא מוכר ⇐ `404`.

התוצאה נשמרת לזמן שמוגדר בקונפיג. אחריו ה-`trace_id` לא מוכר.

---

## 10. קריאה ישירה לקלאסטר: `POST /v1/cluster-requests`

```json
{ "cluster": "https://cluster-a.net-a:9443", "method": "GET", "path": "/v1/bdbs", "body": null }
```

| שדה | סוג | חובה |
|---|---|---|
| `cluster` | URL | ✅ |
| `method` | str | ✅ |
| `path` | str | ✅ |
| `body` | object או null | |

תשובה: ה-status וה-body של הקלאסטר כמו שהם. בלי rollback.
