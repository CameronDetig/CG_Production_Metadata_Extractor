import json
import unittest
from pathlib import Path
from release import object_key, plan_changes, terraform_plan_command, validate_run, validate_manifest


class ReleaseSafetyTests(unittest.TestCase):
    def test_destructive_change_rejected(self):
        for actions in [['delete'], ['delete', 'create'], ['create', 'delete']]:
            with self.assertRaises(ValueError):
                plan_changes({'resource_changes': [{'address': 'aws_db_instance.db', 'change': {'actions': actions}}]})

    def test_adoption_rejects_effective_change(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'timeout': 180}, 'after': {'timeout': 120}}}]}
        with self.assertRaises(ValueError):
            plan_changes(plan, adoption=True)
        self.assertEqual(len(plan_changes(plan)), 1)

    def test_sensitivity_only_import_difference(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'environment': 'same'}, 'after': {'environment': 'same'}}}]}
        self.assertEqual(plan_changes(plan, adoption=True), [])

    def test_untrusted_run_rejected(self):
        config = {'workflow': '.github/workflows/release.yml', 'repository': 'owner/repo'}
        run = {'conclusion': 'success', 'head_branch': 'main', 'event': 'push',
               'path': config['workflow'], 'repository': {'full_name': config['repository']}}
        validate_run(run, config)
        for key, value in [('event', 'pull_request'), ('head_branch', 'feature'),
                           ('conclusion', 'failure'), ('path', '.github/workflows/other.yml')]:
            with self.assertRaises(ValueError):
                validate_run(dict(run, **{key: value}), config)

    def test_run_key_rejects_path_injection(self):
        with self.assertRaises(ValueError):
            object_key('../state', 1, 'release.tfplan')

    def test_unknown_values_are_not_a_clean_adoption(self):
        plan = {'resource_changes': [{'address': 'aws_lambda_function.app', 'change': {
            'actions': ['update'], 'before': {'x': None}, 'after': {'x': None}, 'after_unknown': {'x': True}}}]}
        with self.assertRaises(ValueError):
            plan_changes(plan, adoption=True)

    def test_expired_or_wrong_commit_plan_rejected(self):
        manifest = {'commit': 'abc', 'repository': 'owner/repo', 'created_at': 100}
        run = {'head_sha': 'abc'}
        config = {'repository': 'owner/repo'}
        validate_manifest(manifest, run, config, 101)
        for now in [99, 86500]:
            with self.assertRaises(ValueError):
                validate_manifest(manifest, run, config, now)
        with self.assertRaises(ValueError):
            validate_manifest(manifest, {'head_sha': 'other'}, config, 101)

    def test_release_plan_skips_refresh_outside_adoption(self):
        runtime = 'runtime.tfvars.json'
        saved = 'release.tfplan'
        self.assertIn('-refresh=false', terraform_plan_command(runtime, saved, refresh=False))
        self.assertNotIn('-refresh=false', terraform_plan_command(runtime, saved, refresh=True))

    def test_import_roles_can_read_resource_tags(self):
        bootstrap = Path(__file__).resolve().parents[1] / 'bootstrap' / 'main.tf.json'
        policies = json.loads(bootstrap.read_text(encoding='utf-8'))['resource']['aws_iam_policy']
        for name in ['plan_0', 'apply_0']:
            statements = json.loads(policies[name]['policy'])['Statement']
            actions = {action for statement in statements for action in statement['Action']}
            self.assertIn('rds:ListTagsForResource', actions)
            self.assertIn('secretsmanager:ListTagsForResource', actions)
            self.assertIn('secretsmanager:ListSecretVersionIds', actions)


if __name__ == '__main__':
    unittest.main()
