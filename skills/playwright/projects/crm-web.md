Local app: `http://app.crm.localhost:3000`, run on the host against the Docker backend.

Route definitions: `src/resources/*/routes.ts`.

Expected port 3000. crm-api pins origins: `.env` `CORS_ALLOWED_ORIGINS` and `SANCTUM_STATEFUL_DOMAINS` list `app.crm.localhost:3000` and `localhost:3000` only, so another port needs those keys extended and a backend restart. Treat 3000 as pinned: stop when another repo holds it. App marker: the page title `CRM` or `<page> - CRM` (`titleTemplate` in `src/app.vue`).
