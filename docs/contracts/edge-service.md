# חוזה: השירות שלנו ⇐ שירות הקצה

מה redis-enterprise-services מצפה לקבל משירות הקצה (cluster-relay): שירות שיושב ברשת של הקלאסטרים, מקבל מאיתנו
בקשה אחת לכל קריאה ל-REST API של קלאסטר, ומעביר אותה. ההתאמה של שירות הקצה לחוזה באחריות הבעלים שלו.

שמות ה-headers וקודי השגיאה נטענים מ-`config/edge.yaml`, ואפשר להחליף אותם בלי שינוי קוד.

---

## 1. רשת וחומת אש

שירות הקצה נמצא ברשת היעד, מאחורי חומת האש של החברה.

| # | דרישה |
|---|---|
| C0a | לכל רשת יש כתובת משלה לשירות הקצה: `edge.networks.<רשת>.url`. רשת בלי `url` נדחית בעליית השירות. רשת שחסרה לגמרי ב-`edge.networks` מתגלה רק בריצה ברקע, בקריאה הראשונה (בדיקת השמות), והפעולה `rejected` עם `internal_error` |
| C0b | אם חומת האש של הרשת דורשת אימות, כל בקשה נושאת שם משתמש וסיסמה (`Basic`) של אותה רשת, ב-header מהקונפיג (`edge.networks.<רשת>.firewall`). הסיסמה מגיעה ממשתנה סביבה. `firewall: null` ⇐ לא נשלח header |
| C0c | אימות חומת האש נפרד מ-`x-cluster-authorization` ולא מתנגש בו |
| C0d | חומת האש לא מחזירה תשובה משלה כשהיא דוחה בקשה: הבקשה פשוט נכשלת. הסיבה בלוגים של חומת האש |
| C0e | אם הכתובת ב-HTTPS, התעודה לא נבדקת. שגיאת TLS יכולה לקרות גם אחרי שהבקשה נשלחה (חומת האש מפענחת ומצפינה מחדש) |

**כישלון תקשורת:** השירות שלנו מבחין בלוג בין "לא נשלח" (חיבור שנדחה, DNS, timeout בהתחברות) לבין "נשלח ולא
ענה" (שגיאת TLS, timeout בקריאה, חיבור שנסגר). בהחלטה שניהם תוצאה לא ידועה, כי "לא נשלח" לא אמין.

---

## 2. הבקשה

```
POST <edge.networks.<רשת>.url>
<header האימות של חומת האש>: Basic <פרטי הרשת>     (אם מוגדר)
x-cluster-method: PUT
x-cluster-url: https://<cluster>:9443/v1/bdbs/7
x-cluster-authorization: Basic <credentials>
traceparent: 00-<trace-id>-<span-id>-<flags>
content-type: application/json
cluster-state-id: 155          (אופציונלי)

<body, כמו שהוא>
```

| # | דרישה | למה |
|---|---|---|
| C1 | ה-URL, כולל query string, מועבר לקלאסטר כמו שהוא | שליפות עם `fields` |
| C2 | ה-body מועבר כמו שהוא | |
| C3 | `traceparent` ממשיך לקלאסטר | מעקב מקצה לקצה. ה-trace הוא של הבקשה שהגיעה אלינו |
| C4 | `cluster-state-id` מועבר לקלאסטר כ-request header, אם נשלח | עדכון מותנה של DB. היום: עדכון ההרשאות על ה-DB |
| C5 | `x-task-id` ו-`x-result-ttl` מועברים לקלאסטר, אם נשלחו | מתוכנן ל-Active-Active: מזהה task של CRDB שאנחנו קובעים. השירות שלנו עוד לא שולח אותם |
| C15 | ה-timeout של שירות הקצה מול הקלאסטר קצר מה-timeout שלנו מולו (שלנו: 35 שניות, `edge.timeout_seconds`) | שירות הקצה עונה ראשון, עם קוד משלו |

---

## 3. תשובה מהקלאסטר

| # | דרישה | למה |
|---|---|---|
| C6 | ה-status, ה-headers וה-body של הקלאסטר מוחזרים בלי שינוי, גם בשגיאה (4xx/5xx) | ההחלטה אצלנו לפי ה-status ולפי `error_code` של הקלאסטר |
| C7 | `cluster-state-id` מוחזר כ-response header | נדרש לעדכון המותנה הבא |
| C8 | ה-schema של שירות הקצה מאפשר את כל התשובות שהשירות שלנו צריך | אחרת תשובה תקינה נחסמת. הרשימה בסעיף 5 |

---

## 4. שגיאה ששירות הקצה עצמו יצר

השירות שלנו צריך להבחין בין שגיאה של הקלאסטר לבין שגיאה של שירות הקצה. למשל, 502 יכול להגיע משניהם.

| # | דרישה |
|---|---|
| C9 | כל תשובה ששירות הקצה יצר בעצמו כוללת `x-edge-error` עם קוד. תשובה מהקלאסטר לעולם לא כוללת אותו |
| C10 | הקודים מבחינים בין מה שבוודאות לא הגיע לקלאסטר לבין מה שאולי בוצע בו |
| C11 | ב-`response_rejected` מוחזר גם ה-status המקורי של הקלאסטר, ב-`x-edge-cluster-status` |

| `x-edge-error` | מתי | הגיע לקלאסטר? | אצלנו | קוד ציבורי |
|---|---|---|---|---|
| `invalid_request` | חסר header או header לא תקין | לא | שגיאה שלנו. לא מנסים שוב | `internal_error` |
| `connection_failed` | לא נפתח חיבור לקלאסטר | לא (לא סומכים על זה) | תוצאה לא ידועה | `cluster_unavailable` |
| `response_rejected` | הקלאסטר ענה, והתשובה לא עמדה ב-schema | כן | תוצאה לא ידועה | `cluster_unavailable` |
| כל קוד אחר (למשל `timeout`) | | לא ידוע | תוצאה לא ידועה | `cluster_unavailable` |

**תוצאה לא ידועה:** הצעד בודק בקלאסטר אם הפעולה בוצעה.
- **יצירה:** אם ה-uid כבר נשמר מהתשובה, המשאב נחשב קיים, והצעד רק מחכה לסיום הפעולה בקלאסטר. אחרת מחפשים לפי השם.
- **עדכון (ההרשאות על ה-DB):** משווים את הערכים הנוכחיים לחדשים. לא שווים אחרי שה-snapshot כבר נשמר ⇐
  `requires_manual_intervention`.

נמצא ⇐ ממשיכים. לא נמצא ⇐ ניסיון חוזר אחד. הבדיקה מסתיימת בכישלון ודאי (DB ב-`creation-failed`, action שנכשל) ⇐
ביטול, כמו בכל כישלון ודאי. כל מקרה אחר (הבדיקה עצמה נכשלה, או כל כישלון אחרי הניסיון החוזר) ⇐
`requires_manual_intervention`, בלי ביטול.
`x-edge-cluster-status` לא משמש להחלטה.

---

## 5. תשובות שה-schema חייב לאפשר (C8)

**בשימוש היום:**

| endpoint | שיטה | תשובה |
|---|---|---|
| `/v1/bdbs`, `/v1/bdbs/{uid}` | GET (גם עם `fields`), POST, PUT, DELETE | bdb או רשימה |
| `/v1/redis_acls[/{uid}]` | GET, POST, DELETE | ACL או רשימה. ב-DELETE: `{action_uid}` |
| `/v1/roles[/{uid}]` | GET, POST, DELETE | role או רשימה. ב-DELETE: `{action_uid}` |
| `/v1/users[/{uid}]` | GET, POST, DELETE | user או רשימה |
| `/v1/actions/{uid}` | GET | action |
| כל endpoint | כל שיטה | גוף שגיאה של הקלאסטר: `{error_code, description}` |

**נדרש לתכונות המתוכננות:**

| endpoint | לשם מה |
|---|---|
| `/v1/bdbs` עם `dry_run`, `/v1/cluster/stats/last` | בחירת קלאסטר לפי מקום |
| `/v1/crdbs[/{guid}]`, `/v1/crdb_tasks/{id}` | Active-Active |
| PUT על `/v1/redis_acls`, `/v1/roles`, `/v1/users`, ו-`/v1/users/password` | עריכה |
| `/v1/cluster` | Active-Active (FQDN של הקלאסטר) |
| כל endpoint, כל תשובה | קריאה ישירה לקלאסטר |

---

## 6. סודות

| # | דרישה | למה |
|---|---|---|
| C12 | שירות הקצה לא רושם ללוג את `x-cluster-authorization` | |
| C13 | שירות הקצה לא רושם ללוג סודות מתוך גוף התשובה, גם ב-failure log | תשובות bdb ו-crdb כוללות `authentication_admin_pass` ו-`authentication_redis_pass` בטקסט גלוי |
| C14 | שירות הקצה לא רושם ללוג את גוף הבקשה של `POST /v1/bdbs` ו-`POST /v1/users`, ובהמשך גם `POST /v1/crdbs`, `PUT /v1/users` ו-`/v1/users/password` | הם כוללים סיסמאות. ב-`POST /v1/bdbs`: הסיסמה של `default_user` (`authentication_redis_pass`) |

הדרישות חלות על כל רמות הלוג חוץ מ-DEBUG.
