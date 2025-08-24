#!/usr/bin/env python3
# File: decorators.py
# Description: Décorateurs défensifs pour le pipeline Synergesis

import logging
import time
import functools
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Union, TypeVar, cast

# Configuration du logging
logger = logging.getLogger('decorators')

# Type générique pour les fonctions décorées
F = TypeVar('F', bound=Callable[..., Any])


def fallback_property(property_name: str, fallback_source: Optional[str] = None, 
                      fallback_value: Any = None, log_level: int = logging.WARNING) -> Callable[[F], F]:
    """
    Décorateur qui gère les propriétés manquantes dans un dictionnaire.
    
    Si la propriété spécifiée est manquante, le décorateur essaie d'abord de la récupérer
    depuis une source alternative (fallback_source), puis utilise une valeur par défaut (fallback_value).
    
    Args:
        property_name: Nom de la propriété à vérifier
        fallback_source: Chemin vers une propriété alternative (format: "key1.key2.key3")
        fallback_value: Valeur par défaut à utiliser si la propriété est manquante
        log_level: Niveau de logging pour les messages (default: WARNING)
        
    Returns:
        Fonction décorée qui gère les propriétés manquantes
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Identifier l'argument qui pourrait contenir la propriété
            data = None
            if args and isinstance(args[0], dict):
                data = args[0]
            elif 'data' in kwargs and isinstance(kwargs['data'], dict):
                data = kwargs['data']
            elif 'glyph_data' in kwargs and isinstance(kwargs['glyph_data'], dict):
                data = kwargs['glyph_data']
            elif len(args) > 1 and isinstance(args[1], dict):
                data = args[1]
            
            # Si aucun dictionnaire n'est trouvé, exécuter la fonction normalement
            if data is None:
                return func(*args, **kwargs)
            
            # Vérifier si la propriété est présente
            if property_name not in data or data[property_name] is None or data[property_name] == "":
                used_fallback = True
                
                # Essayer d'utiliser la source alternative
                if fallback_source:
                    try:
                        value = data
                        for key in fallback_source.split('.'):
                            if isinstance(value, dict) and key in value:
                                value = value[key]
                            else:
                                value = None
                                break
                        
                        if value is not None and value != "":
                            data[property_name] = value
                            logger.log(log_level, f"Propriété '{property_name}' manquante, utilisation de '{fallback_source}': {value}")
                            return func(*args, **kwargs)
                    except Exception as e:
                        logger.log(log_level, f"Erreur lors de l'accès à '{fallback_source}': {e}")
                
                # Utiliser la valeur par défaut
                data[property_name] = fallback_value
                logger.log(log_level, f"Propriété '{property_name}' manquante, utilisation de la valeur par défaut: {fallback_value}")
            else:
                used_fallback = False
            
            # Exécuter la fonction avec les données modifiées
            result = func(*args, **kwargs)
            
            # Si le résultat est un dictionnaire, ajouter l'information sur l'utilisation du fallback
            if isinstance(result, dict):
                result['used_fallback'] = used_fallback
            
            return result
        
        return cast(F, wrapper)
    
    return decorator


def validate_required_properties(required_properties: List[str], 
                                 raise_exception: bool = False,
                                 arg_name: str = 'data') -> Callable[[F], F]:
    """
    Décorateur qui valide la présence de propriétés requises dans un dictionnaire.
    
    Args:
        required_properties: Liste des propriétés requises
        raise_exception: Si True, lève une exception en cas de propriété manquante
        arg_name: Nom de l'argument contenant le dictionnaire à valider
        
    Returns:
        Fonction décorée qui valide les propriétés requises
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Identifier l'argument qui contient le dictionnaire à valider
            data = None
            if arg_name in kwargs and isinstance(kwargs[arg_name], dict):
                data = kwargs[arg_name]
            elif args and isinstance(args[0], dict):
                data = args[0]
            elif len(args) > 1 and arg_name == 'data' and isinstance(args[1], dict):
                data = args[1]
            
            # Si aucun dictionnaire n'est trouvé, exécuter la fonction normalement
            if data is None:
                return func(*args, **kwargs)
            
            # Vérifier les propriétés requises
            missing_properties = [prop for prop in required_properties if prop not in data or data[prop] is None]
            
            if missing_properties:
                message = f"Propriétés requises manquantes: {', '.join(missing_properties)}"
                logger.warning(message)
                
                if raise_exception:
                    raise ValueError(message)
            
            # Exécuter la fonction
            return func(*args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator


def timing_and_logging(func: F) -> F:
    """
    Décorateur qui mesure et journalise le temps d'exécution d'une fonction.
    
    Args:
        func: Fonction à décorer
        
    Returns:
        Fonction décorée avec mesure du temps d'exécution
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        func_name = func.__name__
        
        logger.info(f"Début de l'exécution de {func_name}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Fin de l'exécution de {func_name} en {execution_time:.3f} secondes")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Erreur lors de l'exécution de {func_name} après {execution_time:.3f} secondes: {e}")
            logger.error(traceback.format_exc())
            raise
    
    return cast(F, wrapper)


def retry(max_attempts: int = 3, delay: float = 1.0, 
          backoff: float = 2.0, exceptions: tuple = (Exception,)) -> Callable[[F], F]:
    """
    Décorateur qui réessaie une fonction en cas d'échec.
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives (en secondes)
        backoff: Facteur multiplicatif pour le délai entre les tentatives
        exceptions: Tuple d'exceptions à intercepter
        
    Returns:
        Fonction décorée avec mécanisme de réessai
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 1
            current_delay = delay
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(f"Échec après {max_attempts} tentatives: {e}")
                        raise
                    
                    logger.warning(f"Tentative {attempt}/{max_attempts} échouée: {e}. Nouvelle tentative dans {current_delay:.2f} secondes.")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
        
        return cast(F, wrapper)
    
    return decorator


def transaction(func: F) -> F:
    """
    Décorateur qui exécute une fonction dans une transaction Neo4j.
    
    Si un paramètre tx est déjà fourni, la fonction est exécutée avec cette transaction.
    Sinon, une nouvelle transaction est créée.
    
    Args:
        func: Fonction à décorer
        
    Returns:
        Fonction décorée avec gestion de transaction
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs) -> Any:
        # Vérifier si une transaction est déjà fournie
        if 'tx' in kwargs and kwargs['tx'] is not None:
            return func(self, *args, **kwargs)
        
        # Vérifier si le connecteur Neo4j est disponible
        if not hasattr(self, 'neo4j_connector') or self.neo4j_connector is None:
            logger.error("Connecteur Neo4j non disponible")
            raise ValueError("Connecteur Neo4j non disponible")
        
        # Créer une nouvelle transaction
        with self.neo4j_connector.driver.session() as session:
            with session.begin_transaction() as tx:
                kwargs['tx'] = tx
                return func(self, *args, **kwargs)
    
    return cast(F, wrapper)


# Fonction principale pour les tests
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exemple d'utilisation du décorateur fallback_property
    @fallback_property("description", fallback_value="Description par défaut")
    def process_data(data):
        return f"Traitement des données: {data['description']}"
    
    # Test avec une propriété manquante
    result = process_data({})
    print(result)  # Devrait utiliser la valeur par défaut
    
    # Test avec une propriété présente
    result = process_data({"description": "Description personnalisée"})
    print(result)  # Devrait utiliser la valeur fournie
