# User management

Administrators can create, update, disable, reset passwords for, and delete
dashboard users. Operators and viewers receive HTTP 403 from these APIs and
cannot open the Users page.

## Endpoints

All routes require a dashboard JWT from an `admin` account.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/users` | List users, ordered by username |
| `POST` | `/api/v1/users` | Create a user |
| `PUT` | `/api/v1/users/{user_id}` | Update full name, role, and active flag |
| `PATCH` | `/api/v1/users/{user_id}/password` | Reset password |
| `PATCH` | `/api/v1/users/{user_id}/status` | Enable or disable |
| `DELETE` | `/api/v1/users/{user_id}` | Delete a user |

Responses never include `password_hash`. Passwords are stored with bcrypt.

## Validation

- Username: unique, 3–30 characters, starting with a letter or digit
- Password: 8–72 characters
- Role: `admin`, `operator`, or `viewer`

## Safety rules

- An administrator cannot delete their own account.
- An administrator cannot disable their own account.
- The last active administrator cannot be demoted, disabled, or deleted.

These cases return HTTP 409 with `cannot_delete_self`, `cannot_disable_self`, or
`last_active_admin`.

## Dashboard

The Users page supports search, role filters, and active/inactive filters.
Create, edit, password reset, disable, and delete use dialogs. Delete, disable,
and password reset ask for confirmation before the API call is sent.
