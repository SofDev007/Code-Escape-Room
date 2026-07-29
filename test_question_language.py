"""Self-check for the in-language question filter used by AI generation.
Run: python test_question_language.py"""
from api_routes.admin import question_in_language

# No code snippet → always kept (nothing contradicts the language).
assert question_in_language({'question': 'What is a pointer?'}, 'C')
assert question_in_language({'question': 'x', 'code': None}, 'Python')
assert question_in_language({'question': 'x', 'code': 'null'}, 'Python')

# Correct-language snippets are kept.
assert question_in_language({'code': 'def f():\n    print(1)'}, 'Python')
assert question_in_language({'code': 'SELECT name FROM users WHERE age > 18'}, 'SQL')
assert question_in_language({'code': '#include <stdio.h>\nint main(){ printf("hi"); }'}, 'C')

# Wrong-language snippets are rejected (2+ markers of another language, none of target).
assert not question_in_language({'code': '#include <stdio.h>\nint main(){ printf("hi"); }'}, 'Python')
assert not question_in_language({'code': 'SELECT name FROM users WHERE age > 18'}, 'Python')

# Ambiguous / marker-less snippet → kept (never discard on a weak signal).
assert question_in_language({'code': 'x = y + 1'}, 'Python')

print("OK: all question_in_language cases pass")
