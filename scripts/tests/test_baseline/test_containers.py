import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_baseline import containers, spec, state
from test_baseline.errors import Fault


CONFIG = {
    "services": {
        "php": {"container_name": "pi-php", "depends_on": {"mariadb": {}, "redis": {}}},
        "mariadb": {"container_name": "pi-mariadb"},
        "redis": {"container_name": "pi-redis"},
        "nginx": {"container_name": "pi-nginx", "depends_on": {"php": {}}},
        "gotenberg": {"container_name": "pi-gotenberg"},
    }
}
LABELS = {
    "com.docker.compose.project": "pi-assistant",
    "com.docker.compose.project.working_dir": "/proj/pi",
    "com.docker.compose.project.config_files": "/proj/pi/a.yml,/proj/pi/b.yml",
    "com.docker.compose.service": "php",
}


class FakeDocker:
    def __init__(self, daemon=True, labels=None, down=("php", "mariadb", "redis"), broken=(), heals=()):
        self.daemon = daemon
        self.labels = labels
        self.states = {name: "exited" for name in down}
        self.broken = set(broken)
        self.heals = set(heals)
        self.calls = []
        self.cwds = []

    def row(self, service):
        state = self.states.get(service, "running")
        name = CONFIG["services"][service]["container_name"]

        return {"Service": service, "Name": name, "State": state, "Health": ""}

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        self.cwds.append(kwargs.get("cwd"))
        out, rc = "", 0

        if cmd[:2] == ["docker", "info"]:
            rc = 0 if self.daemon else 1
        elif cmd[:2] == ["docker", "inspect"]:
            rc = 0 if self.labels is not None else 1
            out = json.dumps([{"Config": {"Labels": self.labels}}]) if self.labels is not None else ""
        elif cmd[:2] == ["docker", "restart"]:
            for name in self.heals:
                self.states[name] = "running"
        elif cmd[:2] == ["docker", "logs"]:
            out = "\n".join(f"line {i}" for i in range(1, 9))
        elif "config" in cmd:
            out = json.dumps(CONFIG)
        elif "ps" in cmd:
            names = cmd[cmd.index("json") + 1:]
            out = "\n".join(json.dumps(self.row(name)) for name in names)
        elif "up" in cmd:
            for name in cmd[cmd.index("--wait-timeout") + 2:]:
                if name not in self.broken:
                    self.states[name] = "running"

        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr="boom" if rc else "")

    def ups(self):
        return [call for call in self.calls if "up" in call]


class ContainerNames(unittest.TestCase):
    def test_distinct_names_from_docker_exec_commands_only(self):
        section = spec.Section(full=[
            'docker exec -u "$(id -u):$(id -g)" -w /var/www/html/{dir} pi-php php artisan test',
            "docker exec -w /var/www/html/{dir} pi-php php artisan other",
            "docker exec -w /app/{dir} second_web ls",
            "npm run lint:check",
        ])

        self.assertEqual(containers.containers_of(section), ["pi-php", "second_web"])
        self.assertEqual(containers.container_of(section), "pi-php")
        self.assertEqual(containers.containers_of(spec.Section(full=["npm test"])), [])


class ComposeResolution(unittest.TestCase):
    def test_labels_become_project_files_and_directory(self):
        with tempfile.TemporaryDirectory() as scratch:
            labels = {**LABELS, "com.docker.compose.project.working_dir": scratch}
            target = containers.compose_from_labels(labels)

            self.assertEqual(
                target.args,
                ["-p", "pi-assistant", "-f", "/proj/pi/a.yml", "-f", "/proj/pi/b.yml", "--project-directory", scratch],
            )
            self.assertEqual(target.service, "php")
            self.assertEqual(target.cwd, Path(scratch))

    def test_worktree_baseline_or_missing_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            baseline = Path(scratch) / ".baseline"
            baseline.mkdir()
            linked = Path(scratch) / "wt"
            linked.mkdir()
            (linked / ".git").write_text("gitdir: elsewhere")

            for path in (baseline, linked, Path(scratch) / "gone"):
                labels = {**LABELS, "com.docker.compose.project.working_dir": str(path)}
                self.assertIsNone(containers.compose_from_labels(labels), path)

    def test_missing_labels_are_refused(self):
        self.assertIsNone(containers.compose_from_labels({}))

    def test_missing_container_resolves_through_main_checkout_config(self):
        fake = FakeDocker()

        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(containers.subprocess, "run", fake):
            target, config = containers.resolve_compose("pi-php", scratch)

            self.assertEqual(target.service, "php")
            self.assertEqual(target.args, ["--project-directory", scratch])
            self.assertEqual(target.cwd, Path(scratch))
            self.assertEqual(config, CONFIG)

    def test_stale_service_label_is_replaced_by_container_name_match(self):
        with tempfile.TemporaryDirectory() as scratch:
            stale = {**LABELS, "com.docker.compose.project.working_dir": scratch, "com.docker.compose.service": "renamed"}
            fake = FakeDocker(labels=stale)

            with mock.patch.object(containers.subprocess, "run", fake):
                target, _ = containers.resolve_compose("pi-php", "/elsewhere")

            self.assertEqual(target.service, "php")

    def test_stale_service_label_without_a_name_match_faults(self):
        with tempfile.TemporaryDirectory() as scratch:
            stale = {**LABELS, "com.docker.compose.project.working_dir": scratch, "com.docker.compose.service": "renamed"}
            fake = FakeDocker(labels=stale)

            with mock.patch.object(containers.subprocess, "run", fake):
                with self.assertRaises(Fault):
                    containers.resolve_compose("gone-container", "/elsewhere")

    def test_unknown_container_name_faults(self):
        fake = FakeDocker()

        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(containers.subprocess, "run", fake):
            with self.assertRaises(Fault):
                containers.resolve_compose("nope", scratch)

    def test_inspect_labels_drive_compose_calls(self):
        with tempfile.TemporaryDirectory() as scratch:
            fake = FakeDocker(labels={**LABELS, "com.docker.compose.project.working_dir": scratch})

            with mock.patch.object(containers.subprocess, "run", fake):
                target, _ = containers.resolve_compose("pi-php", "/elsewhere")

            config_call = [call for call in fake.calls if "config" in call][0]

            self.assertEqual(
                config_call[:8],
                ["docker", "compose", "-p", "pi-assistant", "-f", "/proj/pi/a.yml", "-f", "/proj/pi/b.yml"],
            )
            self.assertEqual(fake.cwds[-1], Path(scratch))
            self.assertEqual(target.service, "php")


class HostnameMatching(unittest.TestCase):
    def repo(self, scratch, phpunit="", testing="", env=""):
        for name, text in (("phpunit.xml", phpunit), (".env.testing", testing), (".env", env)):
            if text:
                (Path(scratch) / name).write_text(text)

    def test_hosts_from_env_phpunit_and_urls(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(
                scratch,
                phpunit='<phpunit><php><env name="DB_HOST" value="mariadb"/>\n<env name="DB_URL" value=""/>\n'
                '<server name="SESSION_DRIVER" value="array"/></php></phpunit>',
                testing="REDIS_HOST=redis\nAPP_NAME=gotenberg\n",
                env='GOTENBERG_URL="http://gotenberg:3000/forms"\nMAIL_HOST=127.0.0.1\nexport SCOUT_HOST=redis:6379\n',
            )

            self.assertEqual(containers.referenced_hosts(scratch), {"mariadb", "redis", "gotenberg", "127.0.0.1"})

    def test_phpunit_attribute_order_and_quote_style_do_not_matter(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(
                scratch,
                phpunit="<phpunit><php><env value='redis' name='REDIS_HOST'/>\n"
                '<server value="mariadb" name="DB_HOST"/></php></phpunit>',
            )

            self.assertEqual(containers.referenced_hosts(scratch), {"redis", "mariadb"})

    def test_inline_dotenv_comments_are_dropped(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(scratch, env="REDIS_HOST=redis # cache\nDB_HOST=\"mariadb\" # main\nMAIL_HOST='x y' # q\n")

            self.assertEqual(containers.referenced_hosts(scratch), {"redis", "mariadb", "x y"})

    def test_unparseable_phpunit_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(scratch, phpunit="<phpunit", env="REDIS_HOST=redis\n")

            self.assertEqual(containers.referenced_hosts(scratch), {"redis"})

    def test_matching_adds_hosts_and_dependencies_but_not_unrelated_services(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(scratch, env="DB_HOST=mariadb\nREDIS_HOST=redis\n")

            self.assertEqual(containers.services_needed(CONFIG, "php", scratch), ["php", "mariadb", "redis"])

    def test_host_only_service_is_added_and_dependents_are_not(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(scratch, env="CACHE_HOST=gotenberg\nNGINX_NAME=nginx\n")

            self.assertEqual(containers.services_needed(CONFIG, "php", scratch), ["php", "gotenberg", "mariadb", "redis"])

    def test_db_and_redis_settings_that_are_not_hosts_do_not_match(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(
                scratch,
                env="DB_HOST=mariadb\nDB_CONNECTION=mysql\nDB_DATABASE=redis\nREDIS_CLIENT=gotenberg\nREDIS_PORT=nginx\n",
            )

            self.assertEqual(containers.referenced_hosts(scratch), {"mariadb"})

    def test_non_host_keys_do_not_match(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.repo(scratch, env="APP_NAME=gotenberg\n")

            self.assertEqual(containers.referenced_hosts(scratch), set())


class BringUp(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.main = Path(self.scratch.name)
        (self.main / ".env").write_text("DB_HOST=mariadb\nREDIS_HOST=redis\n")
        self.log = self.main / "containers.log"
        patches = [
            mock.patch.object(containers, "STARTED", []),
            mock.patch.object(containers.time, "sleep", lambda _: None),
            mock.patch.object(containers, "HEALTH_WAIT", 0),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.section = spec.Section(full=["docker exec -w /var/www/html/{dir} pi-php php artisan test"])

    def run_ensure(self, fake):
        with mock.patch.object(containers.subprocess, "run", fake):
            containers.ensure_containers(self.section, self.main, self.log)

    def test_stopped_containers_start_with_services_the_tests_reach(self):
        fake = FakeDocker()

        self.run_ensure(fake)

        up = fake.ups()[0]
        self.assertEqual(up[up.index("--wait-timeout") + 2:], ["php", "mariadb", "redis"])
        self.assertNotIn("nginx", up)
        self.assertIn("--no-recreate", up)
        self.assertEqual(containers.STARTED, ["pi-php", "pi-mariadb", "pi-redis"])
        self.assertEqual(containers.containers_line(), "CONTAINERS started pi-php, pi-mariadb, pi-redis")
        self.assertIn("up -d --wait", self.log.read_text())

    def test_only_the_stopped_one_is_reported(self):
        fake = FakeDocker(down=("redis",))

        self.run_ensure(fake)

        self.assertEqual(containers.STARTED, ["pi-redis"])

    def test_everything_running_runs_nothing_and_reports_nothing(self):
        fake = FakeDocker(down=())

        self.run_ensure(fake)

        self.assertEqual(fake.ups(), [])
        self.assertEqual(containers.containers_line(), "")

    def test_repo_without_docker_command_touches_nothing(self):
        fake = FakeDocker()

        with mock.patch.object(containers.subprocess, "run", fake):
            containers.ensure_containers(spec.Section(full=["npm test"]), self.main, self.log)

        self.assertEqual(fake.calls, [])

    def test_unready_after_up_is_restarted_once_then_passes(self):
        fake = FakeDocker(broken=("redis",), heals=("redis",))

        self.run_ensure(fake)

        restarts = [call for call in fake.calls if call[:2] == ["docker", "restart"]]
        self.assertEqual(restarts, [["docker", "restart", "pi-redis"]])
        self.assertIn("pi-redis", containers.STARTED)

    def test_still_down_after_restart_faults_with_container_and_last_five_log_lines(self):
        fake = FakeDocker(broken=("redis",))

        with self.assertRaises(Fault) as raised:
            self.run_ensure(fake)

        message = str(raised.exception)
        restarts = [call for call in fake.calls if call[:2] == ["docker", "restart"]]
        self.assertEqual(len(restarts), 1)
        self.assertIn("pi-redis", message)
        self.assertIn("line 8", message)
        self.assertIn("line 4", message)
        self.assertNotIn("line 3", message)

    def test_stopped_daemon_faults_before_any_compose_call(self):
        fake = FakeDocker(daemon=False)

        with self.assertRaises(Fault) as raised:
            self.run_ensure(fake)

        self.assertIn("daemon is not running", str(raised.exception))
        self.assertEqual(fake.calls, [["docker", "info"]])

    def test_report_line_is_inserted_after_the_head(self):
        with mock.patch.object(containers, "STARTED", ["game_web", "pi-redis"]):
            wrapped = containers.with_containers("head\nbody\nRESULT clean")

        self.assertEqual(wrapped, "head\nCONTAINERS started game_web, pi-redis\nbody\nRESULT clean")
        self.assertEqual(containers.with_containers("head\nbody"), "head\nbody")
