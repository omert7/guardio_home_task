"""Rule matching functionality for routing Pokemon."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models import PokemonModel, RuleModel

logger = logging.getLogger("pokemon-proxy")

class Operator:
    """Class representing comparison operators for rule matching."""
    EQUALS = '=='
    NOT_EQUALS = '!='
    GREATER_THAN = '>'
    LESS_THAN = '<'
    
    @staticmethod
    def parse(rule_str: str) -> Tuple[str, str, str]:
        """Parse a rule string into field, operator, and value.
        
        Args:
            rule_str: The rule string to parse
            
        Returns:
            Tuple containing field, operator, and value
            
        Raises:
            ValueError: If the rule format is invalid
        """
        if Operator.EQUALS in rule_str:
            field, value = rule_str.split(Operator.EQUALS, 1)
            op = Operator.EQUALS
        elif Operator.NOT_EQUALS in rule_str:
            field, value = rule_str.split(Operator.NOT_EQUALS, 1)
            op = Operator.NOT_EQUALS
        elif Operator.GREATER_THAN in rule_str:
            field, value = rule_str.split(Operator.GREATER_THAN, 1)
            op = Operator.GREATER_THAN
        elif Operator.LESS_THAN in rule_str:
            field, value = rule_str.split(Operator.LESS_THAN, 1)
            op = Operator.LESS_THAN
        else:
            raise ValueError(f"Invalid rule format: {rule_str}")
        
        return field.strip(), op, value.strip()
    
    @staticmethod
    def evaluate(op: str, actual_value: Any, expected_value: Any) -> bool:
        """Evaluate a comparison between two values using the specified operator.
        
        Args:
            op: The operator to use ('==', '!=', '>', '<')
            actual_value: The actual value to compare
            expected_value: The expected value to compare against
            
        Returns:
            bool: Result of the comparison
            
        Raises:
            ValueError: If the operator is unknown
        """
        if op == Operator.EQUALS:
            return actual_value == expected_value
        elif op == Operator.NOT_EQUALS:
            return actual_value != expected_value
        elif op == Operator.GREATER_THAN:
            return actual_value > expected_value
        elif op == Operator.LESS_THAN:
            return actual_value < expected_value
        else:
            raise ValueError(f"Unknown operator: {op}")


class Rule:
    """Class representing a rule for routing Pokemon."""
    
    def __init__(self, rule_config: RuleModel):
        """Initialize a rule from a RuleModel.
        
        Args:
            rule_config: The rule configuration
        """
        self.url = rule_config.url
        self.reason = rule_config.reason
        self.match_rules = rule_config.match
        
    def matches(self, pokemon: PokemonModel) -> bool:
        """Check if the Pokemon matches all the conditions in this rule.
        
        Args:
            pokemon: The Pokemon to check
            
        Returns:
            bool: True if the Pokemon matches all conditions, False otherwise
        """
        if not self.match_rules:
            # Empty match list means match everything
            return True
            
        for rule in self.match_rules:
            if not self._evaluate_rule(rule, pokemon):
                return False
        
        return True
    
    def _evaluate_rule(self, rule: str, pokemon: PokemonModel) -> bool:
        """Evaluate a single match rule against a Pokemon.
        
        Args:
            rule: The rule string to evaluate
            pokemon: The Pokemon to check
            
        Returns:
            bool: True if the Pokemon matches the rule, False otherwise
        """
        try:
            # Parse the rule
            field, op, value = Operator.parse(rule)
            
            # Get the actual value from the Pokemon
            actual_value = getattr(pokemon, field)
            
            # Convert the string value to the appropriate type based on the field
            expected_value = self._convert_value(value, actual_value)
            
            # Evaluate the condition
            return Operator.evaluate(op, actual_value, expected_value)
                
        except Exception as e:
            logger.error(f"Error evaluating rule '{rule}': {str(e)}")
            return False
    
    def _convert_value(self, value: str, actual_value: Any) -> Any:
        """Convert string value to the appropriate type based on the actual value.
        
        Args:
            value: The string value to convert
            actual_value: The actual value to determine the type
            
        Returns:
            The converted value with the appropriate type
        """
        if isinstance(actual_value, bool):
            return value.lower() == 'true'
        elif isinstance(actual_value, int) or isinstance(actual_value, float):
            return int(value) if value.isdigit() else float(value)
        else:
            return value


async def find_matching_rule(pokemon_model: PokemonModel, rules: List[RuleModel]) -> Optional[Rule]:
    """Find the first rule that matches the Pokemon.
    
    Args:
        pokemon_model: The Pokemon to check
        rules: List of rule configurations
        
    Returns:
        Optional[Rule]: The first matching rule, or None if no match
    """
    for rule_config in rules:
        rule = Rule(rule_config)
        if rule.matches(pokemon_model):
            return rule
    
    logger.info(f"No matching rule for Pokemon: {pokemon_model.name}")
    return None 