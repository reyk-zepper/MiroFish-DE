import importlib.util
import os
import pathlib
import unittest
from unittest.mock import patch

CONFIG_PATH = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'config.py'


def reload_config(graph_provider, zep_key=None, extra_env=None):
    env = {
        'GRAPH_PROVIDER': graph_provider,
        'LLM_PROVIDER': 'local',
        'LOCAL_LLM_API_KEY': 'dummy',
        'NEO4J_URI': 'bolt://localhost:7687',
        'NEO4J_USER': 'neo4j',
        'NEO4J_PASSWORD': 'change-me',
        'NEO4J_DATABASE': 'neo4j',
    }
    if zep_key is not None:
        env['ZEP_API_KEY'] = zep_key
    if extra_env:
        env.update(extra_env)

    with patch.dict(os.environ, env, clear=False):
        if zep_key is None:
            os.environ.pop('ZEP_API_KEY', None)
        spec = importlib.util.spec_from_file_location('mirofish_config_under_test', CONFIG_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Config


class GraphProviderConfigTests(unittest.TestCase):
    def test_local_graph_provider_does_not_require_zep_api_key(self):
        Config = reload_config('graphiti_neo4j')

        errors = Config.validate()

        self.assertNotIn('ZEP_API_KEY is not configured', errors)
        self.assertEqual(Config.GRAPH_PROVIDER, 'graphiti_neo4j')
        self.assertEqual(errors, [])

    def test_local_graph_provider_requires_neo4j_config(self):
        Config = reload_config('graphiti_neo4j', extra_env={'NEO4J_PASSWORD': ''})

        errors = Config.validate()

        self.assertIn('NEO4J_PASSWORD is not configured', errors)

    def test_zep_graph_provider_requires_zep_api_key(self):
        Config = reload_config('zep_cloud')

        errors = Config.validate()

        self.assertIn('ZEP_API_KEY is not configured', errors)

    def test_unknown_graph_provider_is_rejected(self):
        Config = reload_config('unknown')

        errors = Config.validate()

        self.assertIn("Unknown GRAPH_PROVIDER 'unknown'. Use one of: zep_cloud, graphiti_neo4j", errors)


if __name__ == '__main__':
    unittest.main()
