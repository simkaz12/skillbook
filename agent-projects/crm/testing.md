base: dev

[crm-api]
focused: docker exec -u "$(id -u):$(id -g)" -w /var/www/html/{dir} crm_web php artisan test <paths> | --filter=<name>

[crm-web]
focused: mise exec node@22.23.3 -- npx vitest run <paths>
