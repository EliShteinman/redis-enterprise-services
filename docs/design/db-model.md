# מודל ה-DB

**סטטוס:** הוחלט, חוץ מהפריטים בסעיף 5
**תאריך:** 2026-10-21
**גרסת DB:** Redis 8.4. ה-modules מובנים בגרסה, ולכן `module_list` לא חלק מהמודל.

---

## 1. כללים

- **כל שדה במודל** יכול לקבל ברירת מחדל מ-`config/database_defaults.yaml`: ערכים כלליים, ודריסות שחלות לפי
  תוויות של הקלאסטר (רשת, סביבה, אתר, סוג או שם; `saga.md` סעיף 1). ה-UI יכול לשלוח ערך לכל שדה, והערך שלו
  דורס את ברירת המחדל. שדה שנשלח כ-`null` נחשב כאילו לא נשלח. אין שדה שנקבע רק מהקונפיג.
- **שדות חובה** הם שדות בלי ברירת מחדל: `name` ו-`memory_size`.
- **שדה שלא במודל** לא נשלח לקלאסטר, והקלאסטר קובע אותו לפי ברירת המחדל שלו.

---

## 2. השדות במודל

| שדה | חובה | ברירת מחדל בקונפיג | הערה |
|---|---|---|---|
| `name` | ✅ | - | |
| `memory_size` | ✅ | - | |
| `version` | | `8.4` | |
| `replication` | | `true`, וב-DEV `false` | |
| `sharding` | | | |
| `shards_count` | | | |
| `shard_key_regex` | | כללי ברירת המחדל של Redis | נשלח רק כש-`sharding` דלוק |
| `data_persistence` | | `aof` | |
| `aof_policy` | | `appendfsync-every-sec` | |
| `snapshot_policy` | | | רלוונטי רק כש-`data_persistence` הוא `snapshot` |
| `eviction_policy` | | | ב-AA, eviction מתחיל ב-80% מהזיכרון (תיעוד) |
| `shards_placement` | | `dense` | |
| `proxy_policy` | | `all-master-shards` | |
| `slave_ha` | | | |

**עריכה:** כל שדה במודל יכול להגיע בבקשת עריכה. מגבלות של התשתית, כמו הקטנת `shards_count` או שינוי `sharding`
ב-AA, הן לא אחריות של הקוד. הקלאסטר דוחה את הבקשה, והשגיאה שלו מוחזרת. רשימת השדות שאי אפשר להחזיר אחורה
(D7) נשארת בקונפיג, כי היא קובעת אם צעד העריכה הוא pivot.

**סיסמת ה-default (נבדק, bdb ו-CRDB):**
- ביצירה נשלחים `default_user: true` ו-`authentication_redis_pass`, עם הסיסמה הקבועה מ-Secret. ב-CRDB הם נשלחים
  ב-`default_db_config`. הם לא שדות במודל, וה-UI לא שולח אותם.
- התוצאה: חיבור בלי סיסמה נדחה (`NOAUTH`), וחיבור עם הסיסמה עובד. ב-AA זה עובד בשני האתרים.
- **`GET /v1/bdbs/{uid}` מחזיר את הסיסמה בטקסט גלוי**, ולכן מסתירים אותה בלוגים וב-saga record.
- אם תצטרך החלפת סיסמה בעתיד: `/v1/bdbs/{uid}/passwords` מוסיף (POST), מחליף (PUT) או מוחק (DELETE) סיסמה.
  אפשר להחזיק שתי סיסמאות במקביל בזמן ההחלפה (נבדק).

**לא נשלחים, ולא במודל:**
- **`port`:** הקלאסטר מקצה פורט אוטומטית, גם ב-AA.
- **`tls_mode`:** אין TLS. החיבור הוא בשם משתמש וסיסמה בלבד.
- **`roles_permissions`:** ה-Saga בונה אותו מהיוזרים.

---

## 3. AA: שדות שחייבים להיות זהים בין האתרים

לפי התיעוד של `crdb/database_config`:

| רמה | שדות | מה המודל עושה |
|---|---|---|
| חייבים להיות זהים, אחרת הסנכרון נכשל | `version`, `sharding`, `shard_key_regex` | חוסם ערך שונה בין קלאסטרים בצירוף |
| מומלץ שיהיו זהים | `memory_size`, `eviction_policy`, `shards_count`, `shards_placement`, `proxy_policy` | מזהיר |
| מותר שיהיו שונים | `data_persistence`, `aof_policy`, `snapshot_policy`, `replication` | לא בשימוש. אצלנו הם זהים |

**אצלנו אין הבדל בין אתרים, חוץ מהיוזרים.** כל הבדל אחר הוא תקלה. כל הערכים נשלחים ב-`default_db_config`,
ו-`instances[].db_config` לא נשלח אף פעם. Redis מאפשר הבדלים (V15), אבל השירות לא משתמש בזה.

---

## 4. נשארו מחוץ למודל

- **אבטחה:** TLS ותעודות לקוח, `data_internode_encryption`, mTLS, `disabled_commands`.
- **פריסה:** OSS Cluster, `oss_sharding`, `rack_aware`, `hash_slots_policy`, `avoid_nodes` ו-`use_nodes`.
- **גיבוי ונתונים:** backup, import, export, Replica Of.
- **AA:** `encryption`, `featureset_version`, `crdt_repl_backlog_size`, `crdt_xadd_id_uniqueness_mode`,
  `crdt_syncer_auto_oom_unlatch`.
- **כוונון פנימי:** חיבורים ו-proxy, סנכרון הדרגתי, defrag, pipeline, `maxclients`, `max_connections`,
  `repl_backlog_size`, `slave_buffer`, `max_aof_file_size`, `recovery_wait_time`.
- **הגדרות פנימיות של יכולות:** search, timeseries, probabilistic, `audit_settings`.
- **ברירות מחדל של Redis שלא צריך לשלוח:** `resp3`, `shard_block_foreign_keys`.
- **סוגים אחרים:** memcached, Redis Flex, שדות deprecated, שדות לקריאה בלבד.

---

## 5. יוזר, ACL ו-role

| משאב | שדה | מקור | הערה |
|---|---|---|---|
| ACL | `name` | נגזר: `{db}-{user}-acl` | |
| ACL | `acl` | **ה-UI, מחרוזת ACL גולמית** (למשל `+@all ~*`) | התכנון הנוכחי |
| role | `name` | נגזר: `{db}-{user}-role` | |
| role | `management` | קונפיג, ברירת מחדל `db_viewer` | |
| role | `resources` | נגזר: `[{type: db, uids: [ה-DB]}]` | מגביל את ה-role ל-DB של היוזר בלבד |
| user | `name` | ה-UI, חובה | המפתח של היוזר. הקלאסטר אוכף ייחודיות, תלוית רישיות (V16). מדיניות שמות: שאלה 15 ב-plan |
| user | `email` | לא נשלח | אין מיילים ליוזרים |
| user | `password` | ה-UI, חובה | |
| user | `auth_method` | קבוע: `regular` | |
| user | `role_uids` | ה-Saga | |

- **יוזר חייב role אחד לפחות.** בלי role הקלאסטר מחזיר `400` (נבדק). לכן ה-role נוצר לפני היוזר.
- **`email_alerts` של יוזר חדש דלוק כברירת מחדל** (נבדק). ראו סעיף 6.
- **יוזר עם `management: none`** מקבל `403` מה-REST API (נבדק).

---

## 6. פתוח

### להחלטה

| שדה | מה פתוח |
|---|---|
| `tags` | יוחלט בהמשך |
| **שינוי `name`** | לא הוחלט, וההחלטה לא רק שלך. אם יתאפשר, השירות משנה גם את שמות ה-ACL וה-role שנגזרים מהשם (`{db}-{user}-acl`, `{db}-{user}-role`), ו-`find_by_key` משתמש בשם החדש. התכנון צריך לאפשר את זה. |
| **התראות** | כל נושא ההתראות עוד לא מוגדר: `email_alerts` של ה-DB, ו-`email_alerts` / `bdbs_email_alerts` של היוזר (דלוק כברירת מחדל ביוזר חדש). יוחלט בהמשך. |

### לבדיקה עתידית

| שדה | מה הוא עושה |
|---|---|
| `auto_upgrade` | מעדכן את גרסת ה-DB אוטומטית אחרי שהקלאסטר מתעדכן |
| `master_persistence` | כותב AOF גם ב-master. כרגע ה-master לא כותב. |
| `crdt_causal_consistency` | ב-AA, מבטיח שעדכונים מגיעים לכל האתרים לפי סדר התלות ביניהם |
| `replication_oom_threshold_percent` | ב-AA, מ-8.4: חוסם כתיבות של לקוחות לפני OOM, כדי שהסנכרון בין האתרים ימשיך |
| `instances[].compression` | ב-AA: רמת הדחיסה של הסנכרון בין האתרים (0–6, ברירת מחדל 3) |
| `mkms` | פקודות multi-key על פני כמה shards. ב-AA לא נתמך. |
| `slave_ha_priority` | הסדר שבו DBs מקבלים replica חדשה אחרי נפילת node |
| `metrics_export_all` | מוציא את כל המטריקות של ה-shards ל-Prometheus |
| `query_performance_factor` | מקצה יותר CPU ל-Search בכל shard. ב-8.x משתנה בלי restart. |
