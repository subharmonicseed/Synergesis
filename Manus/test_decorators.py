#!/usr/bin/env python3
# File: test_decorators.py
# Description: Tests unitaires pour les décorateurs défensifs

import unittest
import logging
from unittest.mock import MagicMock, patch
import time

from decorators import (
    fallback_property,
    validate_required_properties,
    timing_and_logging,
    retry,
    transaction,
    PropertyNotFoundException
)

# Configuration du logging pour les tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test_decorators')


class TestFallbackProperty(unittest.TestCase):
    """Tests pour le décorateur fallback_property."""

    def test_property_exists(self):
        """Test quand la propriété existe."""
        @fallback_property("test_prop")
        def test_func(data):
            return data["test_prop"]
        
        result = test_func({"test_prop": "value"})
        self.assertEqual(result, "value")

    def test_property_missing_with_fallback(self):
        """Test quand la propriété est manquante et un fallback est fourni."""
        @fallback_property("test_prop", fallback_value="default")
        def test_func(data):
            return data["test_prop"]
        
        result = test_func({})
        self.assertEqual(result, "default")

    def test_fallback_source(self):
        """Test quand la propriété est récupérée depuis une source alternative."""
        @fallback_property("test_prop", fallback_source="metadata.source.alt_prop")
        def test_func(data):
            return data["test_prop"]
        
        result = test_func({
            "metadata": {
                "source": {
                    "alt_prop": "alternative_value"
                }
            }
        })
        self.assertEqual(result, "alternative_value")

    def test_named_argument(self):
        """Test avec un argument nommé."""
        @fallback_property("test_prop", fallback_value="default")
        def test_func(other_arg, data=None):
            return data["test_prop"]
        
        result = test_func("ignored", data={})
        self.assertEqual(result, "default")


class TestValidateRequiredProperties(unittest.TestCase):
    """Tests pour le décorateur validate_required_properties."""

    def test_all_properties_present(self):
        """Test quand toutes les propriétés requises sont présentes."""
        @validate_required_properties(["prop1", "prop2"])
        def test_func(glyph_data):
            return "success"
        
        result = test_func({"prop1": "value1", "prop2": "value2"})
        self.assertEqual(result, "success")

    def test_missing_properties_no_exception(self):
        """Test quand des propriétés sont manquantes mais sans lever d'exception."""
        @validate_required_properties(["prop1", "prop2"])
        def test_func(glyph_data):
            return "success"
        
        result = test_func({"prop1": "value1"})
        self.assertEqual(result, "success")

    def test_missing_properties_with_exception(self):
        """Test quand des propriétés sont manquantes et une exception est levée."""
        @validate_required_properties(["prop1", "prop2"], raise_exception=True)
        def test_func(glyph_data):
            return "success"
        
        with self.assertRaises(PropertyNotFoundException):
            test_func({"prop1": "value1"})

    def test_custom_arg_name(self):
        """Test avec un nom d'argument personnalisé."""
        @validate_required_properties(["prop1"], arg_name="custom_arg")
        def test_func(custom_arg):
            return "success"
        
        result = test_func({"prop1": "value1"})
        self.assertEqual(result, "success")


class TestTimingAndLogging(unittest.TestCase):
    """Tests pour le décorateur timing_and_logging."""

    @patch('decorators.logger')
    def test_successful_execution(self, mock_logger):
        """Test d'une exécution réussie."""
        @timing_and_logging
        def test_func():
            return "success"
        
        result = test_func()
        self.assertEqual(result, "success")
        
        # Vérifier que les logs ont été appelés
        self.assertEqual(mock_logger.info.call_count, 2)
        self.assertEqual(mock_logger.error.call_count, 0)

    @patch('decorators.logger')
    def test_execution_with_error(self, mock_logger):
        """Test d'une exécution avec erreur."""
        @timing_and_logging
        def test_func():
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            test_func()
        
        # Vérifier que les logs d'erreur ont été appelés
        self.assertEqual(mock_logger.info.call_count, 1)
        self.assertEqual(mock_logger.error.call_count, 1)
        self.assertEqual(mock_logger.debug.call_count, 1)


class TestRetry(unittest.TestCase):
    """Tests pour le décorateur retry."""

    def test_successful_execution(self):
        """Test d'une exécution réussie du premier coup."""
        mock_func = MagicMock(return_value="success")
        
        @retry(max_attempts=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 1)

    def test_retry_until_success(self):
        """Test d'une exécution qui réussit après plusieurs tentatives."""
        mock_func = MagicMock(side_effect=[ValueError("Error 1"), ValueError("Error 2"), "success"])
        
        @retry(max_attempts=3, delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_all_attempts_fail(self):
        """Test quand toutes les tentatives échouent."""
        mock_func = MagicMock(side_effect=ValueError("Persistent error"))
        
        @retry(max_attempts=3, delay=0.01)
        def test_func():
            return mock_func()
        
        with self.assertRaises(ValueError):
            test_func()
        
        self.assertEqual(mock_func.call_count, 3)

    def test_specific_exceptions(self):
        """Test avec des exceptions spécifiques."""
        mock_func = MagicMock(side_effect=[ValueError("Error"), "success"])
        
        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def test_func():
            return mock_func()
        
        result = test_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)


class TestTransaction(unittest.TestCase):
    """Tests pour le décorateur transaction."""

    def test_with_neo4j_connector(self):
        """Test avec un connecteur Neo4j."""
        # Créer des mocks pour Neo4j
        mock_tx = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.begin_transaction.return_value = mock_tx
        mock_session.begin_transaction.__enter__ = MagicMock(return_value=mock_tx)
        mock_session.begin_transaction.__exit__ = MagicMock(return_value=None)
        
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        
        mock_neo4j = MagicMock()
        mock_neo4j.driver = mock_driver
        
        # Fonction décorée
        @transaction
        def test_func(neo4j_connector, tx=None):
            return f"Transaction: {tx}"
        
        # Exécuter la fonction
        result = test_func(mock_neo4j)
        
        # Vérifier que la transaction a été utilisée
        self.assertTrue(mock_driver.session.called)
        self.assertTrue(mock_session.begin_transaction.called)

    def test_without_neo4j_connector(self):
        """Test sans connecteur Neo4j."""
        @transaction
        def test_func(some_arg):
            return "No transaction"
        
        result = test_func("test")
        self.assertEqual(result, "No transaction")

    def test_with_class_method(self):
        """Test avec une méthode de classe."""
        class TestClass:
            def __init__(self):
                self.neo4j_connector = MagicMock()
                self.neo4j_connector.driver = MagicMock()
                
                # Configurer les mocks pour la session et la transaction
                mock_tx = MagicMock()
                mock_session = MagicMock()
                mock_session.__enter__ = MagicMock(return_value=mock_session)
                mock_session.__exit__ = MagicMock(return_value=None)
                mock_session.begin_transaction.return_value = mock_tx
                mock_session.begin_transaction.__enter__ = MagicMock(return_value=mock_tx)
                mock_session.begin_transaction.__exit__ = MagicMock(return_value=None)
                
                self.neo4j_connector.driver.session.return_value = mock_session
            
            @transaction
            def test_method(self, arg1, tx=None):
                return f"Method with tx: {tx}, arg: {arg1}"
        
        # Créer une instance et appeler la méthode
        instance = TestClass()
        result = instance.test_method("test_arg")
        
        # Vérifier que la transaction a été utilisée
        self.assertTrue(instance.neo4j_connector.driver.session.called)


if __name__ == '__main__':
    unittest.main()
