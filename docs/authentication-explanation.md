# RecallDSA Authentication Explanation

This document explains the JWT authentication implementation added to RecallDSA. It describes which files were changed, why each change was made, how the code works, and how the frontend and backend communicate.

## 1. Authentication design

RecallDSA uses JSON Web Tokens through `djangorestframework-simplejwt`.

The implementation uses two tokens:

- **Access token:** Short-lived token used on normal API requests. It expires after 30 minutes.
- **Refresh token:** Longer-lived token used to obtain a new access token. It expires after 1 day.

The frontend sends the access token in this format:

```http
Authorization: Bearer <access-token>
```

This is why Django REST Framework can identify the logged-in user as `request.user` inside an authenticated view.

## 2. Why this method was used

### JWT instead of Django sessions

The application has a React frontend and Django REST API running as separate applications. JWT is appropriate here because:

- The API does not need to store a session for every browser client.
- React can attach the token to API requests using the `Authorization` header.
- The API can authenticate requests independently of the frontend page state.
- The same API can later be used by mobile apps or other clients.

### SimpleJWT instead of custom token code

`djangorestframework-simplejwt` was used instead of manually creating JWTs because it already provides:

- Secure token creation and validation.
- Expiration handling.
- Refresh-token support.
- Django REST Framework authentication integration.
- Token blacklisting support.

Writing this logic manually would create unnecessary security and maintenance risk.

### Django's built-in user model

The existing Django user model is used through `get_user_model()`. This keeps authentication compatible with Django's password hashing, authentication backends, admin, and user relationships such as `UserProblem.user`.

## 3. Backend files changed

### `backend/backend/settings.py`

This file configures JWT authentication globally.

#### Added blacklist application

```python
'rest_framework_simplejwt.token_blacklist',
```

This enables the database tables needed to mark refresh tokens as invalid after logout.

#### Added DRF authentication configuration

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
```

This tells Django REST Framework to inspect the `Authorization: Bearer ...` header on API requests.

When a valid access token is found, SimpleJWT identifies the related user and sets:

```python
request.user
```

If the token is missing or invalid on a view protected by `IsAuthenticated`, the API returns an authentication error instead of executing the view.

#### Added token lifetime settings

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

These settings mean:

- Access tokens are valid for 30 minutes.
- Refresh tokens are valid for 1 day.
- Refresh tokens are rotated when used.
- Older rotated refresh tokens are blacklisted.
- Requests must use the `Bearer` authentication scheme.

For production, the secret key and token lifetime settings should be reviewed according to the deployment's security requirements.

### `backend/backend/urls.py`

This file adds the refresh-token endpoint:

```text
POST /api/token/refresh/
```

SimpleJWT handles this endpoint through `TokenRefreshView`. A frontend can send a refresh token and receive a new access token without asking the user to log in again.

The existing `api/` URL include remains responsible for the custom authentication endpoints in `revise/urls.py`.

### `backend/revise/serializers.py`

This file converts users to and from JSON safely.

#### `UserSerializer`

```python
fields = ['id', 'username', 'email']
```

This controls the user data returned to the frontend. The password is deliberately excluded.

#### `RegisterSerializer`

This serializer accepts:

- `username`
- `email`
- `password`

The password is write-only, has a minimum length of 8 characters, and is never returned in an API response.

Its `create()` method calls:

```python
User.objects.create_user(**validated_data)
```

Using `create_user()` is important because Django hashes the password correctly. Saving a raw password directly would be insecure and would make login fail.

### `backend/revise/views.py`

This file contains the authentication behavior.

#### `register(request)`

Endpoint:

```text
POST /api/auth/register/
```

Flow:

1. The request body is passed to `RegisterSerializer`.
2. Validation checks the required fields and password length.
3. A Django user is created with a hashed password.
4. A refresh token is created for that user.
5. The access token is generated from the refresh token.
6. The user and both tokens are returned.

Successful response shape:

```json
{
  "user": {
    "id": 1,
    "username": "ada",
    "email": "ada@example.com"
  },
  "access": "<access-token>",
  "refresh": "<refresh-token>"
}
```

`AllowAny` is used because a user must be able to register before being authenticated.

#### `login(request)`

Endpoint:

```text
POST /api/auth/login/
```

Flow:

1. The username and password are read from the request.
2. Django's `authenticate()` checks the credentials.
3. If the credentials are invalid, the API returns HTTP 401.
4. If they are valid, new access and refresh tokens are generated.
5. The user and tokens are returned.

Django's authentication system is used here rather than manually comparing passwords. This ensures Django's password hashing and authentication rules are respected.

#### `current_user(request)`

Endpoint:

```text
GET /api/auth/me/
```

This endpoint uses:

```python
@permission_classes([IsAuthenticated])
```

SimpleJWT authenticates the bearer token before the function runs. The authenticated user is then available as:

```python
request.user
```

The endpoint serializes and returns that user.

This is the endpoint the frontend calls when the application starts and an access token already exists in local storage.

#### `logout(request)`

Endpoint:

```text
POST /api/auth/logout/
```

The request must include the refresh token:

```json
{
  "refresh": "<refresh-token>"
}
```

The endpoint calls `blacklist()` on that token. After blacklisting, the same refresh token cannot be used to create another access token.

The endpoint also requires `IsAuthenticated`, so the current access token must be valid when logout is requested.

The response status is HTTP 205, which means the client should reset its local authentication state.

### `backend/revise/urls.py`

This file maps the custom authentication functions to API paths:

| URL | Method | Purpose |
|---|---:|---|
| `/api/auth/register/` | POST | Create a user and return JWT tokens |
| `/api/auth/login/` | POST | Verify credentials and return JWT tokens |
| `/api/auth/logout/` | POST | Blacklist the refresh token |
| `/api/auth/me/` | GET | Return the authenticated user |

The existing `/api/home/` route was not changed to require authentication, so it remains publicly accessible. To protect it later, add `@permission_classes([IsAuthenticated])` to the view.

### `backend/revise/tests.py`

The tests use DRF's `APITestCase` so the authentication endpoints are tested as HTTP APIs.

The tests verify:

- Registration returns HTTP 201.
- Registration returns access and refresh tokens.
- A bearer access token allows `/api/auth/me/` to identify the correct user.
- Logout returns HTTP 205.
- A logged-out refresh token is rejected with HTTP 401.
- Invalid login credentials return HTTP 401.

This protects the most important authentication behavior against accidental regressions.

## 4. Frontend files changed

### `frontend/src/context/AuthContext.js`

This file creates the shared React context object:

```javascript
export const AuthContext = createContext(null)
```

It is separated from the provider so React Fast Refresh can reload component files cleanly during development.

### `frontend/src/context/useAuth.js`

This file exports the `useAuth()` hook. Components can use it to access:

```javascript
const { user, loading, register, login, logout } = useAuth()
```

The hook throws an error if it is used outside `AuthProvider`, which makes incorrect component setup easier to find.

### `frontend/src/context/AuthContext.jsx`

This file contains the frontend authentication state and API calls.

#### Stored authentication state

The access and refresh tokens are stored under:

```text
recalldsa-auth
```

in browser local storage. This allows the user to remain logged in after a page refresh.

The stored value contains only the tokens:

```json
{
  "access": "<access-token>",
  "refresh": "<refresh-token>"
}
```

The current user is loaded from the backend instead of trusting a user object saved in the browser. This means the backend remains the source of truth.

#### `request()` helper

The helper sends JSON requests, parses JSON responses, and converts API errors into JavaScript errors. It also handles HTTP 205 logout responses that have no JSON body.

#### Startup behavior

When `AuthProvider` starts:

1. It reads stored tokens from local storage.
2. If there is an access token, it calls `/api/auth/me/`.
3. If the request succeeds, the returned user is placed in React state.
4. If the request fails, the stored authentication is cleared.

This prevents the UI from treating an expired or invalid token as a valid login.

#### `register()` and `login()`

Both functions send credentials to the backend. When the backend returns tokens, the provider:

1. Saves the tokens in React state.
2. Saves the tokens in local storage.
3. Stores the returned user in React state.

#### `logout()`

The frontend sends the access token in the authorization header and the refresh token in the request body. In a `finally` block it always clears local React state and local storage, even when the access token has already expired.

### `frontend/src/main.jsx`

The application is wrapped with `AuthProvider`:

```jsx
<AuthProvider>
  <App />
</AuthProvider>
```

This makes authentication available to every component rendered inside `App`.

## 5. Complete request flow

### Register

```text
React form
  -> POST /api/auth/register/
  -> Django validates and creates the user
  -> Django returns access + refresh tokens
  -> React stores tokens and user
```

### Login

```text
React form
  -> POST /api/auth/login/
  -> Django authenticates username and password
  -> Django returns access + refresh tokens
  -> React stores tokens and user
```

### Authenticated request

```text
React reads access token
  -> sends Authorization: Bearer <access-token>
  -> SimpleJWT validates the token
  -> DRF sets request.user
  -> protected view uses request.user
```

### Restore login after refresh

```text
React loads stored access token
  -> GET /api/auth/me/
  -> backend validates token
  -> React receives the current user
```

### Logout

```text
React sends access token + refresh token
  -> backend blacklists refresh token
  -> React clears state and local storage
```

## 6. Database migration

The blacklist app requires database tables. The migration was applied with:

```powershell
cd "c:\Full stack Projects\RecallDSA\backend"
python manage.py migrate
```

Run this command in a new environment before using logout.

## 7. Verification commands

Backend tests:

```powershell
cd "c:\Full stack Projects\RecallDSA\backend"
python manage.py test revise.tests
```

Django configuration check:

```powershell
python manage.py check
```

Frontend lint and production build:

```powershell
cd "c:\Full stack Projects\RecallDSA\frontend"
npm run lint
npm run build
```

All of these checks passed after the authentication implementation.

## 8. Important security notes

- Do not commit real production secrets in `settings.py` or `.env`.
- Use HTTPS in production so bearer tokens are encrypted in transit.
- The access token is intentionally short-lived.
- The refresh token must be protected because it can create new access tokens.
- Passwords are hashed by Django and are never returned by the API.
- The current `/api/home/` endpoint is public until `IsAuthenticated` is added to it.
