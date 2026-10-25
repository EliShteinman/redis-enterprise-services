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
| הזדהות | חובה בכל route. השיטה תיקבע בהמשך |
| סינכרוני | כל בקשה מחכה לסיום הפעולה ומחזירה את התוצאה הסופית |
| IDs | ביצירה לא שולחים IDs. הם חוזרים בתשובה, ונשלחים בבקשות הבאות |
| סיסמאות | נשלחות בבקשה, ולא חוזרות אף פעם |

---

## 2. Routes

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
| `replication` | bool | | |
| `sharding` | bool | | |
| `shards_count` | int | | |
| `shard_key_regex` | list | | רק כש-`sharding` הוא `true` |
| `eviction_policy` | str | | |
| `shards_placement` | `dense` / `sparse` | | `dense` |
| `proxy_policy` | str | | `all-master-shards` |
| `slave_ha` | bool | | |

שדה בלי ערך בעמודת ברירת המחדל הוא אופציונלי. אם לא נשלח, ה-DB נוצר עם ברירת המחדל של Redis.

### `body.users[]`

| שדה | סוג | חובה | ברירת מחדל |
|---|---|---|---|
| `users` | list | | `[]` |
| `users[].name` | str | ✅ | |
| `users[].password` | str | ✅ | |
| `users[].acl` | str | ✅ | |

`acl` הוא מחרוזת ACL של Redis, למשל `+@all ~orders:*`.

### תשובה

`201`, עם עץ ה-DB (סעיף 8).

---

## 4. `target` של עריכה ומחיקה

כל הבקשות בסעיפים 5–7 מקבלות את אותו `target`, עם הערכים שחזרו בתשובה ליצירה:

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

תשובה: `200`, עם עץ ה-DB.

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

תשובה: `200`, עם עץ ה-DB.

---

## 7. מחיקה: `POST /v1/databases/delete`

```json
{ "target": { … } }
```

תשובה: `200`, עם `status: succeeded` ו-`database: null`.

---

## 8. התשובה

### הצלחה

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

### כישלון

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

| `status` | משמעות | HTTP |
|---|---|---|
| `rejected` | נדחה לפני ששום דבר השתנה | לפי `error.code` |
| `rolled_back` | נכשל, והכל בוטל. שום דבר לא השתנה | `422` כשהקלאסטר דחה, `502` כשהוא לא זמין |
| `requires_manual_intervention` | נכשל, ולא הכל בוטל. `not_rolled_back` מפרט מה נשאר | `500` |
| `pending_cleanup` | timeout ביצירת AA. התוצאה הסופית בשאילתת הסטטוס | `504` |

`not_rolled_back[]`: `cluster`, `type`, `name`, `uid`, `error`.

### `error.code` ב-`rejected`

| `code` | HTTP | מתי |
|---|---|---|
| `validation_error` | `422` | הבקשה לא עומדת בחוזה. `error.details` לכל שדה |
| `password_rules` | `422` | הפרה של טבלת הסיסמאות (סעיף 6) |
| `unknown_cluster` | `422` | כתובת או יעד לא מוכרים |
| `unauthenticated` | `401` | |
| `database_not_found` | `404` | `db_id` לא נמצא |
| `clusters_mismatch` | `409` | `clusters` לא תואם לאתרים של ה-DB |
| `sites_diverged` | `409` | ב-AA, אתר שונה מהאחרים בשדה שבעריכה |
| `name_taken` | `409` | שם DB או יוזר תפוס |
| `insufficient_resources` | `409` | אין מקום באף קלאסטר מתאים |
| `database_locked` | `409` | פעולה אחרת רצה על ה-DB |
| `configuration_error` | `500` | בעיה בקונפיג של השירות |

---

## 9. סטטוס: `GET /v1/operations/{trace_id}`

מחזיר את אותה תשובה כמו הפקודה (סעיף 8). בזמן ריצה `status` הוא `running`. `trace_id` לא מוכר ⇐ `404`.

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
