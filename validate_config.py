#!/usr/bin/env python3
"""Script to validate config.json against the task requirements."""

import json
import sys
import re
import os
from typing import List, Dict, Any, Tuple

def validate_rule_match_format(match_rule: str) -> Tuple[bool, str]:
    """Validate that a match rule has the correct format.
    
    Args:
        match_rule: The rule string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for allowed operators: ==, !=, >, <
    valid_operators = ['==', '!=', '>', '<']
    
    # First check if there are multiple occurrences of operators
    operator_count = sum(match_rule.count(op) for op in valid_operators)
    if operator_count > 1:
        return False, f"Rule '{match_rule}' contains multiple operators"
    
    # Use regex to properly match operators
    operator_found = None
    field = None
    value = None
    
    for op in valid_operators:
        # Escape special characters for regex
        escaped_op = re.escape(op)
        # Match the operator with optional spaces on either side
        pattern = r'([^=<>]*)\s*' + escaped_op + r'\s*(.*)'
        match = re.match(pattern, match_rule)
        if match:
            operator_found = op
            field = match.group(1).strip()
            value = match.group(2).strip()
            break
    
    if operator_found is None:
        return False, f"Rule '{match_rule}' does not contain any valid operator (==, !=, >, <)"
    
    # Check that field is not empty
    if not field:
        return False, f"Rule '{match_rule}' has an empty field name"
    
    # Check that value is not empty
    if not value:
        return False, f"Rule '{match_rule}' has an empty value"
    
    return True, ""

def validate_config(config_path: str) -> Tuple[bool, List[str]]:
    """Validate the configuration file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            errors.append(f"Config file '{config_path}' does not exist")
            return False, errors
        
        # Try to parse the JSON
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check for 'rules' key
        if 'rules' not in config:
            errors.append("Config is missing required 'rules' key")
            return False, errors
        
        if not isinstance(config['rules'], list):
            errors.append("'rules' must be a list")
            return False, errors
        
        # Validate each rule
        for i, rule in enumerate(config['rules']):
            # Check required keys
            if 'url' not in rule:
                errors.append(f"Rule #{i+1} is missing required 'url' key")
            elif not isinstance(rule['url'], str) or not rule['url']:
                errors.append(f"Rule #{i+1} has an invalid 'url' value")
            
            if 'reason' not in rule:
                errors.append(f"Rule #{i+1} is missing required 'reason' key")
            elif not isinstance(rule['reason'], str):
                errors.append(f"Rule #{i+1} has an invalid 'reason' value")
            
            if 'match' not in rule:
                errors.append(f"Rule #{i+1} is missing required 'match' key")
                continue
            
            if not isinstance(rule['match'], list):
                errors.append(f"Rule #{i+1} 'match' must be a list")
                continue
            
            # Empty match list is allowed (matches everything)
            if not rule['match']:
                continue
            
            # Validate each match rule
            for j, match_rule in enumerate(rule['match']):
                if not isinstance(match_rule, str):
                    errors.append(f"Rule #{i+1}, match rule #{j+1} must be a string")
                    continue
                
                valid, error = validate_rule_match_format(match_rule)
                if not valid:
                    errors.append(f"Rule #{i+1}, match rule #{j+1}: {error}")
        
        return len(errors) == 0, errors
        
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON format: {str(e)}")
        return False, errors
    except Exception as e:
        errors.append(f"Unexpected error: {str(e)}")
        return False, errors

def main():
    """Main function."""
    config_path = os.environ.get('POKEPROXY_CONFIG', 'config.json')
    
    print(f"Validating config file: {config_path}")
    
    # Test validation of some individual rules
    test_rule_validation = [
        "attack>80",           # Valid
        "legendary==true",     # Valid
        "type_one==Fire",      # Valid
        "attack====100",       # Invalid - wrong operator
        "==value",             # Invalid - missing field
        "field==",             # Invalid - missing value
        "field = = value",     # Invalid format
    ]
    
    print("\nTesting rule validation:")
    for rule in test_rule_validation:
        valid, error = validate_rule_match_format(rule)
        status = "✅ Valid" if valid else "❌ Invalid"
        message = f" - {error}" if not valid else ""
        print(f"  {status}: '{rule}'{message}")
    
    print("\nValidating full config file:")
    valid, errors = validate_config(config_path)
    
    if valid:
        print("✅ Configuration is valid and meets all requirements!")
        
        # Print a summary of the rules
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print(f"\nFound {len(config['rules'])} rules:")
        for i, rule in enumerate(config['rules']):
            match_count = len(rule['match'])
            match_desc = f"{match_count} conditions" if match_count > 0 else "ALL Pokemon (no conditions)"
            print(f"  {i+1}. {rule['reason']} -> {rule['url']} ({match_desc})")
            
            # Print details of conditions
            if match_count > 0:
                print("     Conditions:")
                for condition in rule['match']:
                    print(f"     - {condition}")
            print("")
            
        sys.exit(0)
    else:
        print("❌ Configuration has the following errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

if __name__ == "__main__":
    main() 