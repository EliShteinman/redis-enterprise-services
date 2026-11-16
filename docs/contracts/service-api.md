# חוזה: שירות הביניים ⇐ redis-enterprise-services

ה-API ש-redis-enterprise-services חושף לשירות הביניים: מה נשלח לכל route ומה חוזר. אותו חוזה מתואר גם ב-OpenAPI של
השירות (`/docs`), עם תיאור ודוגמה לכל שדה.

**בנוי היום:** יצירת DB באתר אחד, יצירת DB ב-Active-Active (route נפרד, סעיף 3א) ושאילתת סטטוס. **מתוכנן:** סעיף 7.

---

## 1. כללי

| נושא | ערך |
|---|---|
| פורמט | JSON. שדה לא מוכר בגוף הבקשה ⇐ `422 validation_error` |
| מזהה בקשה | header `traceparent` בפורמט W3C, חובה ב-routes של `/v1/`. חסר או לא תקין ⇐ `422 validation_error` על `header.traceparent`. ה-`trace_id` של הפעולה הוא ה-trace id שבו (32 תווי hex) |
| אסינכרוני | פקודה מחזירה מיד `202` עם `trace_id` בלבד. המצב והתוצאה רק בשאילתת הסטטוס (סעיף 5) |
| IDs | ביצירה לא שולחים IDs. הם חוזרים בתוצאה |
| סיסמאות | סיסמה של יוזר נשלחת בבקשה וחוזרת בתוצאה (הקלאסטר לא מחזיר סיסמאות, ולכן חוזרת זו שהוא קיבל). סיסמאות פנימיות של ה-DB ושל הקלאסטר לא חוזרות ולא נשמרות |
| הזדהות | אין עדיין (סעיף 7) |

| route | |
|---|---|
| `POST /v1/databases/create` | יצירת DB באתר אחד |
| `POST /v1/crdbs/create` | יצירת DB ב-Active-Active (סעיף 3א) |
| `GET /v1/operations/{trace_id}` | סטטוס ותוצאה של פעולה, משני הסוגים |
| `GET /health` | `200 {"status": "ok"}`. בלי `traceparent` |

---

## 2. איך פקודה רצה

![שכבת api](../diagrams/03-layer-api.drawio.svg)

1. **בדיקות מקומיות**, בלי פנייה לקלאסטר: מבנה הגוף, כללי שם ה-DB, ושהיעד מתאים לקלאסטר בקונפיג. כשל ⇐ תשובה
   מיידית עם קוד HTTP (סעיף 6).
2. **קבלה:** `202` עם `{"trace_id"}`. הפעולה רצה ברקע. הפקודה לא מחזירה מצב או תוצאה.
3. **תוצאה:** `GET /v1/operations/{trace_id}` עד ש-`status` סופי: `succeeded`, `rejected`, `rolled_back` או
   `requires_manual_intervention`. סטטוס שלא מוכר לקורא אינו סופי.

**אותו trace id פעמיים** לא מתחיל פעולה חדשה, גם עם span id אחר וגם עם גוף אחר. התשובה היא אותו `202` עם
`{"trace_id"}`, ואת המצב קוראים בשאילתת הסטטוס. לכן כל פקודה צריכה trace משלה.
- רק מבנה הגוף נבדק לפני החיפוש לפי trace. גוף שלא עומד בחוזה ⇐ `422`, גם אם כבר יש פעולה עם אותו trace.
  שאר הבדיקות המקומיות רצות רק כשה-trace חדש.
- פקודה שנדחתה מיד לא נשמרת. אותו trace עם גוף מתוקן מתחיל פעולה חדשה.
- אם השירות לא הצליח להעביר את הפקודה לריצה ברקע (למשל באמצע כיבוי), התשובה המיידית `500 internal_error` עם
  `unexpected RuntimeError: ...`, והפעולה נשמרת כ-`rejected` עם `internal_error` וההודעה הקבועה. אותו trace יקבל
  `202`, ושאילתת הסטטוס תראה את התוצאה הזו עד שהיא פגה.
- אחרי שהתוצאה פגה (סעיף 5), אותו trace מתחיל פעולה חדשה.

---

## 3. יצירה: `POST /v1/databases/create`

```json
{
  "target": {
    "site": {"environment": "PROD", "network": "net-a", "site": "NY", "cluster": "generic"}
  },
  "spec": {
    "database": {"name": "orders", "memory_size": 1073741824},
    "users": [
      {"name": "app", "password": "…", "acl_rule": "+@all ~orders:*"}
    ]
  }
}
```

### `target`

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `site` | object | ✅ | אובייקט אחד: האתר שבו ה-DB נוצר |
| `site.environment` | `DEV` / `PROD` / `TEST` | ✅ | |
| `site.network` | str | ✅ | שם הרשת, כמו בקונפיג של השירות |
| `site.site` | str | ✅ | שם האתר, כמו בקונפיג של השירות |
| `site.cluster` | str | ✅ | `generic`, או ה-FQDN של קלאסטר ייעודי, כפי שהוא כתוב בקונפיג של השירות |

**איך נמצא הקלאסטר:** הבקשה מתארת את הקלאסטר ולא יודעת את הכתובת שלו. השירות מתרגם אותו לכתובת לפי
`helm/files/clusters.yaml`, באותם `environment`, `network` ו-`site`: ב-`generic` קלאסטר מסוג `generic`, וב-FQDN
הקלאסטר מסוג `dedicated` עם ה-FQDN הזה. מכאן כל השלבים עובדים עם כתובת הקלאסטר.
- אין קלאסטר מתאים ⇐ `422 no_matching_cluster`.
- בקשה שתקינה לבד, אבל לא תקינה יחד עם ברירות המחדל של הקלאסטר (למשל `sharding: false` מול ברירת מחדל עם
  `shard_key_regex`) ⇐ `500 configuration_error` עם הסיבה. היום אין ברירת מחדל כזו.
- ב-`generic` צריך להיות בדיוק קלאסטר אחד מתאים. יותר מאחד ⇐ `500 configuration_error`. בחירה בין כמה קלאסטרים
  מתוכננת (סעיף 7).

### `spec.database`

| שדה | סוג | חובה |
|---|---|---|
| `name` | str | ✅ |
| `memory_size` | int חיובי (bytes) | ✅ |
| `version` | str | |
| `replication` | bool | |
| `data_persistence` | `disabled` / `aof` / `snapshot` | |
| `aof_policy` | `appendfsync-every-sec` / `appendfsync-always` | רק יחד עם `data_persistence: aof` |
| `snapshot_policy` | list של `{secs, writes}`, שניהם int חיובי | רק יחד עם `data_persistence: snapshot` |
| `sharding` | bool | `true` רק יחד עם `shard_key_regex` |
| `shards_count` | int, 1–512 (התיעוד של Redis) | מעל 1 רק יחד עם `sharding: true` |
| `shard_key_regex` | list של `{regex}` | רק יחד עם `sharding: true` |
| `eviction_policy` | אחד מעשרת הערכים של Redis (`noeviction`, `allkeys-lru`, …) | |
| `shards_placement` | `dense` / `sparse` | |
| `proxy_policy` | `single` / `all-master-shards` / `all-nodes` | |
| `slave_ha` | bool | |

**כללים:** כל שדה עומד קודם בכללים של Redis עצמו (מהסכמה של הקלאסטר, `/v1/jsonschema`, ומבדיקה מול קלאסטר אמיתי), ועליהם
השירות יכול להוסיף כללים מחמירים יותר בקונפיג. ערך שלא עומד בהם נדחה מיד עם `422`, לפני שמתחילה ריצה.

**שם ה-DB:** הכלל של Redis: אותיות באנגלית, ספרות ו-`-`, לא מתחיל ולא נגמר ב-`-`, עד 64 תווים
(`naming.redis.database`). השירות מחמיר לעד 20 תווים (`naming.database`). אחרת ⇐ `422 invalid_name`, והכללים שהופרו
ב-`error.message`.

**ברירות מחדל:** שדה שלא נשלח, או נשלח כ-`null`, מקבל את ברירת המחדל של השירות ליעד (`helm/files/defaults.yaml`).
השירות שולח במפורש כל הגדרה שחשובה לו, גם כשהיא שווה לברירת המחדל של Redis, כדי ששינוי של Redis, או ברירת מחדל שונה
ל-DB ול-CRDB, לא ישנו התנהגות בלי תכנון. יש שני סטים מלאים זה לצד זה, `single_site` ו-`active_active` (ערכים וערכי
מצב שמירה), ושום ערך של סט אחד לא חל על הסוג השני. סביבה, רשת, אתר או קלאסטר ב-`helm/files/clusters.yaml` יכולים
לדרוס כל ערך, לכל סוג בנפרד. היום, בשני הסטים אותו ערך, אלא אם השורה אומרת אחרת:

| שדה | ברירת מחדל |
|---|---|
| `version` | `8.4` |
| `replication` | `true`, וב-`DEV` `false` |
| `data_persistence` | `aof` |
| `aof_policy` | `appendfsync-every-sec`, רק כש-`data_persistence` הוא `aof` |
| `snapshot_policy` | `[{"secs": 3600, "writes": 1}]`, רק כש-`data_persistence` הוא `snapshot` |
| `shards_placement` | `dense` |
| `proxy_policy` | `all-master-shards` |
| `sharding` | `false` |
| `shards_count` | `1` |
| `slave_ha` | `false` |
| `eviction_policy` | `volatile-lru`, וב-Active-Active `noeviction` (מה ש-Redis נותן לכל סוג, נשלח במפורש) |

`aof_policy` או `snapshot_policy` שנשלחים בבקשה בלי `data_persistence` של אותו מצב ⇐ `422` מיד, לפני שמתחילה ריצה.
כך גם `sharding: true` בלי `shard_key_regex` (Redis דוחה אותו), ו-`shard_key_regex` או `shards_count` מעל 1 בלי
`sharding: true`. ערכים שרק הקלאסטר יכול לבדוק (למשל זיכרון גדול מהקלאסטר, או `version` שלא קיים) נבדקים בקלאסטר, וכשהוא
דוחה, התוצאה היא `rolled_back` עם `cluster_request_failed`.

### `spec.users[]`

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `users` | list | | ברירת מחדל `[]`. כל שם פעם אחת |
| `users[].name` | str | ✅ | בלי `-` (המפריד בשמות ה-ACL וה-role). הכלל של Redis: ASCII בלי `" & < >`, עד 255 תווים (`naming.redis.user`). ושמות ה-ACL וה-role שנגזרים ממנו (`{db}-{user}-acl`, `{db}-{user}-role`) חייבים את הכלל של Redis לשמות אלה: אותיות, ספרות, רווח ו-`_ . @ # ; , ( ) [ ] -`, עד 255 תווים (`naming.redis.acl_and_role`). אחרת ⇐ `422 invalid_name` |
| `users[].password` | str | ✅ | לפחות 8 תווים: ה-`password_min_length` הנמוך ביותר של Redis. קלאסטר שמוגדר עם מינימום גבוה יותר דוחה סיסמה קצרה ממנו |
| `users[].acl_rule` | str | ✅ | כלל ACL של Redis, למשל `+@all ~orders:*`. התחביר נבדק מיד: מילים מופרדות ברווח, `+@category`, `-@category`, `+command`, `-command\|sub`, `~keys`, `%R~keys`, `%W~keys`, `%RW~keys` (כל סדר וכל רישיות, עם תבנית אחרי `~`), `&channels`, `allkeys`, `allcommands`, `nocommands`, `resetkeys`, `allchannels`, `resetchannels`, `on`, `off`, ו-selectors בסוגריים, בלי `on` ו-`off` בתוכם (נבדק מול קלאסטר אמיתי). הגדרות סיסמה (`>`, `<`, `#`, `nopass`, `resetpass`, `reset`) נדחות: הסיסמה מגיעה מ-`password`. שהפקודות והקטגוריות קיימות בודק הקלאסטר |

### מה נוצר בקלאסטר

1. ה-DB, עם הסיסמה של `default_user` מהשירות.
2. לכל יוזר: ACL בשם `{db}-{user}-acl` עם ה-`acl_rule` שלו, role בשם `{db}-{user}-role`, והיוזר עם ה-role.
3. קישור כל role ל-ACL שלו על ה-DB.

לפני שמשהו נוצר, השירות בודק בכל קלאסטר של הבקשה שכל השמות האלה פנויים: ה-DB, היוזרים, ה-ACLs וה-roles. בכל
יצירה, גם באתר בודד, שם ה-DB נבדק גם מול שמות ה-CRDBs. שם תפוס באתר כלשהו ⇐ `rejected` עם `name_taken`.

**אם צעד נכשל בוודאות,** כל מה שכבר נוצר נמחק בסדר הפוך, וההרשאות על ה-DB חוזרות לערכים הקודמים. התוצאה
`rolled_back`.

**אם לא ידוע אם צעד בוצע** (למשל timeout מול הקלאסטר), השירות בודק בקלאסטר. אם הוא לא יכול לקבוע מה קרה, הוא לא
מבטל כלום, והתוצאה `requires_manual_intervention`. כך גם כשביטול נכשל.

## 3א. יצירת Active-Active: `POST /v1/crdbs/create`

route נפרד ליצירת DB אחד על כמה אתרים (CRDB). אין שדה שבוחר סוג: ה-route קובע. הריצה (סעיף 2), הקבלה, הכישלון
והסטטוסים (סעיף 4), שאילתת הסטטוס (סעיף 5) והשגיאות (סעיף 6) זהים ליצירה באתר אחד, חוץ ממה שכתוב כאן.

```json
{
  "target": {
    "sites": [
      {"environment": "PROD", "network": "net-a", "site": "NY", "cluster": "generic"},
      {"environment": "PROD", "network": "net-a", "site": "TLV", "cluster": "generic"}
    ]
  },
  "spec": {
    "crdb": {"causal_consistency": false, "encryption": false, "compression": 3},
    "database": {"name": "orders", "memory_size": 1073741824},
    "users": [
      {"name": "app", "password": "…", "acl_rule": "+@all ~orders:*"}
    ]
  }
}
```

### `target`

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `sites` | list | ✅ | אחד או יותר, כולם באותה `network` ועל קלאסטרים שונים. השירות לא מגביל את המספר; הקלאסטר מגביל את `id` של instance ל-31, ויותר מזה לא נבדק. האתר הראשון מתאם את היצירה |
| `sites[]` | object | ✅ | אותו אובייקט כמו `target.site` בסעיף 3: `environment`, `network`, `site`, `cluster` |

כל אתר מתורגם לקלאסטר כמו בסעיף 3, עם אותן שגיאות (`no_matching_cluster`, `configuration_error`). בנוסף:
- אתרים ביותר מ-`network` אחת ⇐ `422 mixed_networks`. סביבה מעורבת לא נבדקת.
- שני אתרים שמתורגמים לאותו קלאסטר ⇐ `422 duplicate_sites`. שני קלאסטרים שונים עם אותו FQDN או אותו host,
  או עם סיסמה שונה ל-`default_user`, ⇐ `500 configuration_error`: הטעות בקונפיג של הקלאסטרים, לא בבקשה.
- ברירות מחדל שנותנות הגדרות שונות לאתרים שונים, של ה-DB או של ה-CRDB ⇐ `500 configuration_error`, לפני ששום דבר נוצר.
  ההודעה מונה את השדות השונים. זה קורה בעיקר כשהבקשה מערבבת סביבות (למשל אתר DEV ואתר PROD באותה רשת, ש-`replication`
  שלהם שונה): הטעות בבקשה, אבל הקוד `configuration_error` (`known_failure`). שליחת השדות שבהודעה במפורש בבקשה עוקפת
  את זה. כשמצב השמירה שונה, ההודעה לא מונה את `aof_policy` ו-`snapshot_policy` (הם לא נשלחים יחד), אלא את `data_persistence`
  ואת שאר השדות השונים.

`mixed_networks` ו-`duplicate_sites` חוזרים רק מה-route הזה.

### `spec.crdb`

ההגדרות של ה-CRDB עצמו. האובייקט לא חובה, וכל שדה בו לא חובה.

| שדה | סוג | חובה | הערה |
|---|---|---|---|
| `causal_consistency` | bool | | |
| `encryption` | bool | | |
| `compression` | int, 0–6 | | ערך אחד לכל ה-instances |

שדה שלא נשלח, או נשלח כ-`null`, מקבל את ברירת המחדל של השירות: `database_defaults.active_active.crdb`
ב-`helm/files/defaults.yaml`, ורק סביבה או רשת ב-`helm/files/clusters.yaml` יכולות לדרוס אותה (לא אתר ולא קלאסטר, כי CRDB
פרוס על כמה אתרים). ערך שנשלח בבקשה קודם לקונפיג. היום: `causal_consistency: false`, `encryption: false`,
`compression: 3`. ההגדרות נשלחות לקלאסטר תמיד במפורש, וחייבות לצאת זהות לכל האתרים.

### `spec.database` ו-`spec.users[]`

אותם מודלים ואותם כללים כמו בסעיף 3. ברירות המחדל של ה-DB מהסט `active_active`.

### מה נוצר בקלאסטרים

CRDB אחד עם DB מקומי בכל אתר, היוזרים, ה-ACLs וה-roles בכל אתר (כל role מוגבל ל-DB המקומי של האתר
שלו), וכשיש יוזרים, PATCH אחד ל-CRDB שקושר בכל אתר כל role ל-ACL שלו. ל-`default_user` אותה סיסמה בכל האתרים.

בדיקת השמות הפנויים, הביטול וההתערבות הידנית כמו בסעיף 3, על כל הקלאסטרים של הבקשה.

---

## 4. התשובה

![מודלי ה-API](../diagrams/19-api-models-create.drawio.svg)

### קבלה (`202`)

```json
{"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}
```

### הצלחה

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "succeeded",
  "database": {
    "kind": "single_site",
    "name": "orders",
    "memory_size": 1073741824,
    "cluster": {
      "cluster": "cluster-a.net-a", "cluster_url": "https://cluster-a.net-a:9443",
      "environment": "PROD", "network": "net-a", "site": "NY",
      "access": {
        "endpoints": [ {"dns_name": "redis-12000.cluster-a.net-a", "port": 12000, "addr": ["10.0.0.5"]} ]
      },
      "db": {
        "db_uid": 7,
        "settings": {"name": "orders", "memory_size": 1073741824, "version": "8.4.0", "replication": true,
                     "data_persistence": "aof", "aof_policy": "appendfsync-every-sec", "…": "…"},
        "permissions": [
          {"user_uid": 12, "user_name": "app", "user_password": "S3cure-Passw0rd",
           "acl_uid": 9, "acl_rule": "+@all ~orders:*", "role_uid": 4, "role_name": "orders-app-role"}
        ]
      }
    }
  }
}
```

כל ערך של ה-DB, של היוזר, של ה-ACL ושל ה-role נקרא מהקלאסטר. אין ערך שמגיע מהבקשה, חוץ מהסיסמה: הקלאסטר אף פעם לא מחזיר סיסמה,
ולכן חוזרת הסיסמה שהקלאסטר קיבל כשיצר את היוזר. `cluster` (ה-FQDN של הקלאסטר), `cluster_url`, `environment`, `network` ו-`site` מגיעים
מהקונפיג. ביצירה באתר אחד `kind` הוא תמיד `single_site`.

| שדה | הערה |
|---|---|
| `database.kind` | סוג ה-DB. ב-route הזה תמיד `single_site` |
| `database.name`, `database.memory_size` | כפי שה-DB שמר אותם |
| `database.cluster` | אובייקט אחד: הקלאסטר שעליו ה-DB נוצר |
| `cluster.cluster` | ה-FQDN של הקלאסטר, כפי שהוא כתוב בקונפיג |
| `cluster.access.endpoints[]` | איך מתחברים: `dns_name`, `port`, `addr`. לפחות אחד, וכל אחד מלא |
| `cluster.db.db_uid` | ה-uid של ה-DB בקלאסטר |
| `cluster.db.settings` | כל שדות מודל היצירה (`spec.database`), כפי שה-DB שמר אותם אחרי שהפך ל-active |
| `cluster.db.permissions[]` | לכל יוזר: היוזר, ה-ACL וה-role שלו, שנוצרים ונמחקים יחד, כל אחד עם ה-uid שלו. הקישור role ↔ ACL שלהם נבדק ב-DB שנקרא בסוף |

### הצלחה ב-Active-Active

אותה מעטפת, ו-`database` עם `kind: "active_active"` (מקוצר: השדות של כל ענף כמו למעלה):

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "succeeded",
  "database": {
    "kind": "active_active",
    "name": "orders",
    "memory_size": 1073741824,
    "crdb": {
      "guid": "d71cefce-4e31-41fd-b654-37cbb2f39a01",
      "causal_consistency": false,
      "encryption": false,
      "featureset_version": 12,
      "protocol_version": 1,
      "default_db_config": {"name": "orders", "memory_size": 1073741824, "replication": true, "eviction_policy": "noeviction", "default_user": true, "tags": ["…"], "port": 12000, "tls_mode": "disabled", "…": "…"}
    },
    "clusters": [
      {"cluster": "cluster-a.net-a", "cluster_url": "https://cluster-a.net-a:9443", "environment": "PROD", "network": "net-a", "site": "NY",
       "instance_id": 1, "compression": 3,
       "access": {"endpoints": ["…"]}, "db": {"db_uid": 7, "settings": {"…": "…"}, "permissions": ["…"]}},
      {"cluster": "cluster-b.net-a", "cluster_url": "https://cluster-b.net-a:9443", "environment": "PROD", "network": "net-a", "site": "TLV",
       "instance_id": 2, "compression": 3,
       "access": {"endpoints": ["…"]}, "db": {"db_uid": 4, "settings": {"…": "…"}, "permissions": ["…"]}}
    ]
  }
}
```

כל ענף מגיע מה-DB המקומי באותו אתר, עם היוזר, ה-ACL וה-role שנוצרו בו. `kind` הוא תמיד `active_active`.

| שדה | הערה |
|---|---|
| `database.kind` | סוג ה-DB. ב-route הזה תמיד `active_active` |
| `database.name`, `database.memory_size` | כפי שה-DB שמר אותם |
| `database.crdb` | ההגדרות של ה-CRDB עצמו, כפי שהוא שמר אותן |
| `crdb.guid` | ה-guid של ה-CRDB |
| `crdb.causal_consistency`, `crdb.encryption` | כמו שנשלחו: הם נבדקים, וערך אחר מבטל את היצירה |
| `crdb.featureset_version`, `crdb.protocol_version` | נקבעים ב-Redis. `null` כשהקלאסטר לא החזיר אותם |
| `crdb.default_db_config` | כל מה שהשירות שלח, בלי סיסמאות, ועוד השדות שהקלאסטר ממלא בעצמו (`port`, `module_list`, `tls_mode`, ו-`isSystem` בכל tag) |
| `database.clusters[]` | ענף לכל קלאסטר, לפי סדר ה-`sites` בבקשה |
| `clusters[].instance_id` | ה-`id` של ה-instance של ה-CRDB בקלאסטר הזה. השירות מתאים instance לענף לפי `cluster_url`, כשהוא משווה בלי רישיות ועם הפורט ברירת המחדל של הסכמה, ובודק שכל instance שייך לאחד הענפים |
| `clusters[].compression` | של ה-instance, כמו שנשלח: נבדק, וערך אחר מבטל את היצירה |
| שאר השדות של `clusters[]` | אותו ענף כמו `database.cluster` באתר אחד: `cluster`, `cluster_url`, `environment`, `network`, `site`, `access`, `db` |

**איזה סוג חזר:** `GET /v1/operations/{trace_id}` מחזיר פעולה משני ה-routes. בהצלחה, `database.kind` אומר איזה מבנה
חזר: `single_site` עם `cluster`, או `active_active` עם `crdb` ו-`clusters[]`. כל עוד אין הצלחה `database` הוא `null`,
ושאר הגוף זהה בשני הסוגים.

**מאיפה הערכים:** כל אובייקט חייב לחזור מלא כבר בתשובה ליצירה שלו: כל שדה שנשלח חוזר עם ערך. השדות שהקלאסטר אף
פעם לא מחזיר מוגדרים בקונפיג (`unreturned_fields`, היום רק סיסמת היוזר). אחרי עדכון ההרשאות, צעד אחרון קורא את ה-DB
המלא, ובודק שיש ערך לכל שדות מודל היצירה, ל-`uid`, ל-`status` ול-`endpoints`, שכל endpoint מלא, ושההרשאות שנקבעו
נמצאות ב-`roles_permissions`. אובייקט לא מלא, שדה בלי ערך, DB בלי endpoint עם `dns_name`,
`port` ו-`addr`, או הרשאות שלא נמצאות ב-DB, הם כישלון ודאי (`incomplete_cluster_object`, בציבורי `cluster_request_failed`): הכל מתבטל.

### כישלון

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "status": "rolled_back",
  "database": null,
  "error": {
    "code": "cluster_request_failed",
    "kind": "known_failure",
    "message": "POST https://cluster-a.net-a:9443/v1/bdbs was refused with status 400 (invalid_schema)",
    "cluster_url": "https://cluster-a.net-a:9443",
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

**שדות שתמיד קיימים** (חובה בסכמה): `trace_id`, `status` ו-`database`, שהוא `null` כל עוד אין הצלחה. `error` ו-`not_rolled_back`
מופיעים רק כשיש להם ערך.

**`error`:** השגיאה של הצעד שעצר את הפעולה. `cluster_url` ו-`cluster_error_code` מופיעים רק ב-`cluster_request_failed`,
`cluster_unavailable` ו-`cluster_timeout`. `cluster_error_code` מופיע רק כשהקלאסטר החזיר קוד שגיאה משלו.

**`error.kind`:** מה עושים עם השגיאה. כל קוד ממופה לסוג אחד (`operation.error_kind_by_code`):

| `kind` | משמעות |
|---|---|
| `customer_fixable` | הלקוח מבין ומתקן לבד, למשל שם תפוס או שם לא חוקי |
| `known_failure` | התמיכה מבינה את הסיבה מהקוד, למשל קלאסטר לא זמין. ב-`cluster_unavailable` וב-`cluster_timeout` אחרי ביטול מלא, אפשר לנסות שוב מאוחר יותר |
| `needs_investigation` | צריך לעקוב אחרי ה-trace לאורך השרשרת: השירות, הריליי והקלאסטר |

`requires_manual_intervention` הוא תמיד `needs_investigation`, בלי קשר לקוד. קוד שאין לו סוג בקונפיג מתפרסם
כ-`needs_investigation`. קורא שמקבל סוג שהוא לא מכיר (סוג שיתווסף בעתיד) צריך לקרוא אותו כ-`needs_investigation`. הסוג
של כל קוד בטבלה שבסעיף 6.

**`error.message`:** טקסט של השירות, לא גוף גולמי ממי שמתחת. השגיאות שהשירות מכיר מקבלות הודעה קבועה שאומרת מה נכשל
ואיפה, למשל `POST <url> was refused with status 409 (name_already_exists)`. הגוף המלא של הריליי, של הקלאסטר ושל
action שנכשל נרשם בלוג של השירות תחת ה-trace. רק שגיאה לא צפויה, שאף טיפול לא תפס, עולה עם הפרטים הגולמיים שלה:
`unexpected <type>: <text>` (`api.unexpected_error_message`). זו החלטה: הטקסט הוא של השגיאה עצמה, בלי סינון, ולכן
הוא יכול להכיל ערכים, למשל שגיאת אימות של pydantic שמציגה את הקלט שלה.

**`not_rolled_back[]`:** מה שנשאר בקלאסטר.
- ב-`rolled_back`: רשימה ריקה.
- ב-`requires_manual_intervention`: מה שנשאר, כולל משאב שלא ידוע אם נוצר (`uid: null`, והשגיאה של הצעד). השדה
  לא מופיע אחרי קריסה שהסריקה זיהתה (הסריקה לא בונה אותו), או כשה-record של הריצה לא נקרא. כשה-record נקרא אבל אי
  אפשר לבנות ממנו את התוצאה, השדה מופיע עם כל מה שה-record מראה שנוצר (גם אחרי ריצה שהצליחה). הקוד הוא `internal_error`, חוץ ממקרה
  שבו ה-record לא נקרא: אז הקוד הוא של השגיאה שקטעה את הריצה.
- ב-`rejected`: לא מופיע.

| שדה | הערה |
|---|---|
| `cluster_url` | כתובת ה-API של הקלאסטר |
| `resource_type` | `crdb` (ה-Active-Active עצמו, עם ה-DBs המקומיים; רק אחרי `POST /v1/crdbs/create`), `database`, `acl`, `role`, `user` או `permissions` (הקישור של roles ל-ACLs על ה-DB) |
| `crdb_guid` | חסר כשהוא ריק. רק אחרי `POST /v1/crdbs/create`, ב-`crdb` וב-`permissions` של Active-Active: ה-guid של ה-CRDB. ב-`crdb` חסר כשלא ידוע אם ה-CRDB נוצר. פריט `crdb`, ופריט `permissions` של Active-Active (שמכסה את כל האתרים), מדווחים על הקלאסטר המתאם (האתר הראשון) |
| `name` | שם המשאב. ב-`permissions` וב-`crdb`: שם ה-DB |
| `uid` | ה-uid בקלאסטר, או `null` כשלא ידוע אם המשאב נוצר. ב-`permissions`: ה-uid של ה-DB. ב-`crdb` וב-`permissions` של Active-Active תמיד `null`: מה שמזהה אותם הוא `crdb_guid` |
| `last_error` | `"<code>: <message>"` של השגיאה האחרונה (של הביטול אם נכשל, אחרת של הצעד), או `null` |

---

## 5. סטטוס: `GET /v1/operations/{trace_id}`

`200` עם המצב הנוכחי (סעיף 4). `trace_id` שאינו 32 תווי hex קטנים, או שכולו אפסים ⇐ `422 validation_error` על
`path.trace_id`. `trace_id` לא מוכר ⇐ `404 operation_not_found`. גוף השגיאות כאן הוא `{"trace_id", "error"}`, בלי `status`
(סעיף 6), כדי ש-`404` לא ייקרא כמו פעולה שנדחתה.

**כמה זמן התוצאה נשמרת:** `succeeded`, `rejected` ו-`rolled_back` נשמרים 7 ימים (`state.finished_ttl_seconds`),
ואחר כך ה-`trace_id` לא מוכר. `requires_manual_intervention` נשמר עד שמטפלים בו ידנית.

**קריסה:** אם ה-pod שהריץ פעולה נפל, pod אחר מזהה את זה תוך כדקה או שתיים ומסמן אותה:
- `rejected` עם `internal_error`, אם הריצה עוד לא התחילה (לא נוצר כלום);
- `rolled_back` עם `internal_error`, אם הריצה כבר הסתיימה בביטול מלא ורק שמירת הפעולה אבדה;
- אחרת `requires_manual_intervention` עם `internal_error`, גם אם בפועל עוד לא נוצר כלום, וגם אם הריצה הצליחה ורק שמירת
  הפעולה אבדה (ה-DB קיים, אבל `database` הוא `null`).

**נעילה אחרי `requires_manual_intervention`:** בדרך כלל הנעילה על ה-DB ועל היוזרים נשארת, גם אחרי קריסה. עד שמטפלים
בפעולה ידנית, כל פקודה על אותם שמות באותו קלאסטר מסתיימת ב-`resources_locked`. יוצא מן הכלל: הריצה עצמה הסתיימה
ב-`succeeded` או ב-`rolled_back`, ורק הפעולה סומנה `requires_manual_intervention`: ב-`succeeded` כשה-pod נפל לפני ששמר
את הפעולה, ובשניהם כשאת התוצאה לא היה אפשר לבנות מה-record. ה-record הסופי כבר נכתב, ולכן הנעילה משתחררת, ופקודות חדשות על אותם שמות לא
נחסמות.

---

## 6. שגיאות

תשובה מיידית עם שגיאה:
- **בפקודה** (`POST /v1/databases/create` או `POST /v1/crdbs/create`): בנויה כמו כישלון בסטטוס, `{"trace_id", "status": "rejected", "database": null, "error"}`,
  כי הפקודה נדחתה ושום דבר לא השתנה.
- **בכל השאר** (שאילתת הסטטוס, כתובת לא קיימת, method שגוי): `{"trace_id", "error"}`, בלי `status`, כי אין פעולה שנדחתה.
  `trace_id` הוא של הבקשה עצמה: מה-`traceparent`, או, בלי `traceparent` תקין, של ה-trace שהשירות פתח לבקשה.

גם כאן יש ב-`error` את `kind` (סעיף 4), לפי הטבלה למטה. `not_found`, `method_not_allowed` ו-`http_error` הם
`needs_investigation`, כי הם מצביעים על באג בצד הקורא.

ב-`validation_error` יש גם `error.details`: רשימה של `{location, message}` לכל שדה שלא עומד בחוזה, למשל
`body.spec.database.memory_size` או `header.traceparent`.

| `code` | `kind` | איפה | מתי |
|---|---|---|---|
| `validation_error` | `customer_fixable` | מיד, `422` | הבקשה לא עומדת בחוזה |
| `invalid_name` | `customer_fixable` | מיד, `422` | שם ה-DB לא עומד בכללי השמות |
| `no_matching_cluster` | `customer_fixable` | מיד, `422` | אין קלאסטר שמתאים ליעד |
| `mixed_networks` | `customer_fixable` | מיד, `422` | רק ב-`POST /v1/crdbs/create`: אתרים ביותר מרשת אחת |
| `duplicate_sites` | `customer_fixable` | מיד, `422` | רק ב-`POST /v1/crdbs/create`: שני אתרים שמתורגמים לאותו קלאסטר |
| `not_found` | `needs_investigation` | מיד, `404` | כתובת לא קיימת |
| `operation_not_found` | `known_failure` | מיד, `404` | `trace_id` לא מוכר, או שהתוצאה שלו כבר פגה |
| `method_not_allowed` | `needs_investigation` | מיד, `405` | method שהכתובת לא מקבלת |
| `http_error` | `needs_investigation` | מיד, עם ה-status של ה-HTTP | שגיאת HTTP אחרת של ה-framework, שאין לה קוד משלה |
| `configuration_error` | `known_failure` | מיד `500`, או בסטטוס | בעיה בקונפיג של השירות, למשל כמה קלאסטרים `generic` לאותו יעד. בסטטוס רק כרשת ביטחון: רשת בלי ריליי נדחית כבר בעלייה |
| `internal_error` | `needs_investigation` | מיד `500`, או בסטטוס | שגיאה לא צפויה, או שגיאה פנימית בלי קוד ציבורי משלה. שגיאה לא צפויה (שאף טיפול לא תפס): `message` הוא `unexpected <type>: <text>`, גם מיד וגם בסטטוס (חוץ מכשל בהעברה לרקע, שנשמר עם ה-`message` הקבוע). שגיאה פנימית מוכרת: מיד `message` קבוע (`internal error`); בסטטוס, ה-`message` של השגיאה שעצרה (של הצעד, או של השגיאה שקטעה את הריצה כשלצעד אין שגיאה משלו, גם כשה-record לא נקרא); אחרי קריסה, ה-`message` הקבוע. הפרטים בלוג לפי `trace_id` |
| `name_taken` | `customer_fixable` | בסטטוס, `rejected` | שם של DB, יוזר, ACL או role תפוס באחד הקלאסטרים, או שם ה-DB תפוס על ידי CRDB |
| `resources_locked` | `known_failure` | בסטטוס, `rejected` | פעולה אחרת על אותו DB או אותם יוזרים, באחד הקלאסטרים של הבקשה, לא הסתיימה תוך 30 שניות |
| `cluster_request_failed` | `known_failure` | בסטטוס | הקלאסטר דחה בקשה, DB הגיע ל-`creation-failed`, פעולה בקלאסטר הסתיימה ב-`failed`, `cancelled` או `aborted`, task של CRDB הסתיים ב-`failed` או `canceled` (ההודעה מונה כל אתר שנכשל לפי ה-host של ה-`cluster_url` שלו; `cluster_url` הוא הקלאסטר המתאם, ו-`cluster_error_code` מופיע רק כשהמתאם עצמו נכשל), או אובייקט שנקרא מהקלאסטר לא מחזיק את מה שנשלח או נקבע (`incomplete_cluster_object`) |
| `cluster_unavailable` | `known_failure` | בסטטוס | הקלאסטר או שירות הקצה לא זמינים, או שהתשובה לא קריאה |
| `cluster_timeout` | `known_failure` | בסטטוס | הקלאסטר לא סיים פעולה בזמן, למשל DB שלא הגיע ל-`active`, או task של CRDB שעוד רץ (הוא עוד עלול להסתיים) |

אלה הקודים היחידים שחוזרים. בסכמה הם רשימות סגורות (`enum`): ב-`error` של הסטטוס `PublicErrorCode`, כלומר כל
הקודים חוץ מחמשת הקודים של ה-API (`validation_error`, `not_found`, `operation_not_found`, `method_not_allowed`,
`http_error`); בפועל `invalid_name`, `no_matching_cluster`, `mixed_networks` ו-`duplicate_sites` חוזרים רק מיד. ב-`error` של התשובה המיידית הרשימה כוללת
את כל הקודים. שגיאה פנימית אחרת חוזרת כ-`internal_error`. המיפוי מהקודים הפנימיים ב-`helm/files/service.yaml`.

---

## 7. מתוכנן

לא בנוי עדיין. העיצוב ב-`docs/design/planned.md`.

| נושא | מה ישתנה בחוזה |
|---|---|
| בחירת קלאסטר | ב-`generic` השירות יבחר קלאסטר שיש בו מקום מבין כמה. קוד חדש `insufficient_resources` |
| הזדהות | `Authorization` בכל route, אחרת `401 unauthenticated` |
| Active-Active: עריכה, מחיקה, הוספה והסרה של אתר | היצירה בנויה (סעיף 3א). כל השאר ב-routes משלו |
| Active-Active | route נפרד, `POST /v1/crdbs/create`, עם `target: {sites: [...]}`. היצירה באתר אחד לא משתנה. בתוצאה `kind: "active_active"`, אובייקט `crdb` ו-`clusters[]` עם ענף לכל קלאסטר. סטטוס חדש, `pending_cleanup`, כשהיצירה נקטעה וניקוי האתרים עוד רץ. הוא לא סופי |
| `Location` בתשובת `202` | כותרת לראוט הסטטוס: בסיס הכתובת מהקונפיג, והנתיב מהשירות |
| עריכה ומחיקה: היעד | יעד לכל סוג, מהתוצאה של היצירה, שונה מה-`target` של יצירה. באתר אחד: `target: {cluster_url, db_uid}`. ב-Active-Active: `target: {crdb_guid, clusters}` |
| עריכה ומחיקה: קודים | `database_not_found` בסטטוס (`rejected`). ב-Active-Active גם `clusters_mismatch` ו-`sites_diverged` |
| עריכת DB | `POST /v1/databases/update` |
| עריכת יוזרים | `POST /v1/databases/users`, עם רשימת היוזרים המלאה. סיסמה חסרה או מיותרת ⇐ `422 password_rules` |
| מחיקה | `POST /v1/databases/delete` |
| קריאה ישירה לקלאסטר | `POST /v1/cluster-requests`, בלי rollback |
