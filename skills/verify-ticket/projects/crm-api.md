Test commands come from the scope's testing.md. `crm_web` is the container name of the compose service `php_fpm`.

List exports are queued, and no local worker runs them. `exportList()` pushes `CsvExportJob` onto a shared redis list, which can hold other people's jobs, so never drain a shared queue.
- To prove an export, trigger it from the UI and move only your own job ids to a scratch list (RPUSH, then LREM by exact value).
- Run `docker exec -u www-data -e HOME=/tmp crm_web php artisan queue:work redis --queue=<scratch> --stop-when-empty --tries=1`.
- Read the CSV from the app's `storage/app/public/exports/`.
- Afterwards, delete the CSVs and the notification job entries each export adds to `default`.
