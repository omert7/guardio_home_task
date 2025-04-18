"""Tests for rule matching functionality."""

import pytest
from app.core.rules import Operator, Rule
from app.models import PokemonModel, RuleModel


@pytest.mark.parametrize("rule_str,expected", [
    ("hit_points==20", ("hit_points", "==", "20")),
    ("type_two!=word", ("type_two", "!=", "word")),
    ("special_defense > 10", ("special_defense", ">", "10")),
    ("generation< 20", ("generation", "<", "20")),
])
def test_operator_parse(rule_str, expected):
    """Test parsing rule strings."""
    field, op, value = Operator.parse(rule_str)
    assert (field, op, value) == expected


@pytest.mark.parametrize("op,actual,expected,result", [
    ("==", 5, 5, True),
    ("==", "fire", "fire", True),
    ("==", True, True, True),
    ("==", 5, 10, False),
    ("!=", 5, 10, True),
    ("!=", "fire", "water", True),
    ("!=", False, True, True),
    ("!=", 5, 5, False),
    (">", 10, 5, True),
    (">", 5, 10, False),
    ("<", 5, 10, True),
    ("<", 10, 5, False),
])
def test_operator_evaluate(op, actual, expected, result):
    """Test evaluating comparisons."""
    assert Operator.evaluate(op, actual, expected) == result


def test_rule_matches_empty_rules():
    """Test that an empty match list matches everything."""
    rule = Rule(RuleModel(url="http://example.com", reason="test"))
    pokemon = PokemonModel()
    assert rule.matches(pokemon)


def test_rule_matches_single_condition():
    """Test matching a single condition."""
    rule = Rule(RuleModel(
        url="http://example.com",
        reason="test",
        match=["legendary==true"]
    ))
    
    # Should match
    pokemon1 = PokemonModel(legendary=True)
    assert rule.matches(pokemon1)
    
    # Should not match
    pokemon2 = PokemonModel(legendary=False)
    assert not rule.matches(pokemon2)


def test_rule_matches_multiple_conditions():
    """Test matching multiple conditions (AND logic)."""
    rule = Rule(RuleModel(
        url="http://example.com",
        reason="test",
        match=[
            "hit_points>50",
            "attack>70",
            "type_one==Fire"
        ]
    ))
    
    # Should match
    pokemon1 = PokemonModel(
        hit_points=60,
        attack=80,
        type_one="Fire"
    )
    assert rule.matches(pokemon1)
    
    # Should not match (one condition fails)
    pokemon2 = PokemonModel(
        hit_points=60,
        attack=60,  # Below threshold
        type_one="Fire"
    )
    assert not rule.matches(pokemon2)
    
    # Should not match (all conditions fail)
    pokemon3 = PokemonModel(
        hit_points=40,
        attack=60,
        type_one="Water"
    )
    assert not rule.matches(pokemon3) 