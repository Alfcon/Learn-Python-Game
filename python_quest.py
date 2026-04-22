"""
================================================================================
  PYTHON QUEST :: COMP1005 Game Mode  (Desktop / Tkinter Edition)
================================================================================

  A retro-arcade style Python trainer built in 100% pure Python.
  Same levels, same vibe, same XP -- now running natively on your machine.

  HOW TO RUN:
      python3 python_quest.py

  That's it. No pip install, no browser, no internet needed after this file
  is on your computer. Tkinter ships with Python.

  Progress saves to:  python_quest_save.json  (next to this file)
================================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font as tkfont
import json
import os
import io
import sys
import re
import random
import traceback
from pathlib import Path

# =============================================================================
#  COLOUR PALETTE  (matches the neon web version exactly)
# =============================================================================
C = {
    'bg':          '#0a0e27',
    'bg_2':        '#141937',
    'neon_green':  '#39ff14',
    'neon_pink':   '#ff2e97',
    'neon_cyan':   '#00f0ff',
    'neon_yellow': '#ffee00',
    'neon_orange': '#ff8c00',
    'text':        '#e6e8ff',
    'dim':         '#7a86c4',
    'card':        '#1a1f3f',
    'card_hover':  '#232a52',
    'border':      '#2d3566',
    'locked':      '#3a3f5c',
    'editor_bg':   '#05060f',
    'output_bg':   '#02030a',
    'error':       '#ff2e97',
}

# =============================================================================
#  FONT STACK  (arcade font if installed, otherwise a clean monospace)
# =============================================================================
def pick_font(preferred_list, size, weight='normal'):
    """Return the first available font family from a list."""
    available = set(tkfont.families())
    for name in preferred_list:
        if name in available:
            return (name, size, weight)
    return ('Courier', size, weight)

# We'll init fonts AFTER Tk is created (Tk needs to exist first).
FONTS = {}

def init_fonts():
    FONTS['arcade_xxs']  = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 8,  'bold')
    FONTS['arcade_xs']   = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 9,  'bold')
    FONTS['arcade_sm']   = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 10, 'bold')
    FONTS['arcade_md']   = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 12, 'bold')
    FONTS['arcade_lg']   = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 14, 'bold')
    FONTS['arcade_xl']   = pick_font(['Press Start 2P', 'Consolas', 'Courier New'], 18, 'bold')
    FONTS['mono']        = pick_font(['JetBrains Mono', 'Consolas', 'Courier New'], 11)
    FONTS['mono_sm']     = pick_font(['JetBrains Mono', 'Consolas', 'Courier New'], 10)
    FONTS['mono_bold']   = pick_font(['JetBrains Mono', 'Consolas', 'Courier New'], 11, 'bold')
    FONTS['code']        = pick_font(['JetBrains Mono', 'Consolas', 'Courier New'], 11)
    FONTS['body']        = pick_font(['JetBrains Mono', 'Segoe UI', 'Helvetica'],   11)
    FONTS['body_bold']   = pick_font(['JetBrains Mono', 'Segoe UI', 'Helvetica'],   11, 'bold')


# =============================================================================
#  STATE & PERSISTENCE
# =============================================================================
SAVE_FILE = Path(__file__).parent / "python_quest_save.json"

DEFAULT_STATE = {
    'cleared': [],     # list of level IDs cleared
    'xp': 0,
    'current_level': None,
    'saved_code': {},  # key -> code string, key = "L{id}_S{idx}" or "..._b"
}

def load_state():
    try:
        if SAVE_FILE.exists():
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge with defaults so new keys work for old saves
                merged = dict(DEFAULT_STATE)
                merged.update(data)
                return merged
    except Exception:
        pass
    return dict(DEFAULT_STATE)

def save_state(state):
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print("Could not save:", e)


# =============================================================================
#  RANK SYSTEM
# =============================================================================
RANKS = [
    (0,   "NOVICE"),
    (80,  "CODER"),
    (180, "HACKER"),
    (300, "ENGINEER"),
    (450, "WIZARD"),
    (620, "ARCHMAGE"),
]

def get_rank(xp):
    rank = RANKS[0][1]
    for threshold, name in RANKS:
        if xp >= threshold:
            rank = name
    return rank


# =============================================================================
#  PYTHON CODE RUNNER
#  -- This replaces Pyodide. We use the real Python interpreter (via exec()),
#     capture stdout/stderr, and swap input() for a popup-based version.
# =============================================================================
def count_input_calls(code):
    """Count input() calls -- used to decide how many prompts to collect."""
    return len(re.findall(r'\binput\s*\(', code))

def extract_input_prompts(code):
    """Pull the prompt string out of each input("...") call, in order."""
    pattern = r'''input\s*\(\s*(?:f?(['"])((?:\\.|(?!\1).)*)\1)?\s*\)'''
    prompts = []
    for m in re.finditer(pattern, code):
        prompts.append(m.group(2) or "")
    return prompts

def has_loop_with_input(code):
    """Does the code have an input() call inside a for/while loop?"""
    return bool(re.search(r'\b(for|while)\b[\s\S]*?input\s*\(', code))


def run_user_code(code, input_provider):
    """
    Execute the user's Python code.

    input_provider:  a function (prompt_text) -> str  that returns the next
                     input value, OR raises KeyboardInterrupt to cancel.

    Returns: (ok: bool, output_text: str)
    """
    # Custom input() that uses our popup provider
    def fake_input(prompt=""):
        if prompt:
            print(prompt, end="")
        try:
            val = input_provider(prompt)
        except KeyboardInterrupt:
            raise
        if val is None:
            print("\n[input() cancelled]")
            return ""
        print(val)
        return val

    stdout_buf = io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = stdout_buf
    sys.stderr = stdout_buf

    # Give the user code a normal-looking namespace.
    namespace = {
        '__name__': '__main__',
        'input': fake_input,
    }

    ok = True
    try:
        exec(compile(code, '<your_code>', 'exec'), namespace)
    except KeyboardInterrupt:
        ok = False
        print("\n\u2298 Run cancelled.")
    except SystemExit:
        # sys.exit() is legal -- treat as normal stop
        pass
    except Exception:
        ok = False
        # Show a clean traceback (hide our wrapper frames)
        tb = traceback.format_exc()
        # Strip internal "File ..." lines that point at this runner
        tb = re.sub(r'File ".*?python_quest\.py.*?\n.*?\n', '', tb)
        print("\n\u2717 ERROR:\n" + tb.strip())
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    return ok, stdout_buf.getvalue()


# =============================================================================
#  LEVEL DATA  -- full port of the JS levels, structure preserved exactly
# =============================================================================
#  Each level:
#     id, num, title, desc, xp, badges, stages[...], quiz{q, options, correct, explain}
#
#  Each stage can have:
#     title        -- stage heading
#     html         -- rich text content (we convert HTML-ish markup to styled text)
#     code         -- {filename, starter}  -> first code editor
#     afterHtml    -- rich text shown AFTER the first code editor
#     code2        -- optional SECOND code editor on the same stage
#     afterHtml2   -- rich text shown AFTER the second code editor
# =============================================================================
LEVELS = [
    # ---------- LEVEL 1 ----------
    {
        'id': 1,
        'num': 'P0 + P1',
        'title': 'Linux Arena & Python Basics',
        'desc': 'Navigate Linux, write your first Python, master print/input/if/loops.',
        'xp': 40,
        'badges': ['LINUX', 'INPUT', 'IF/ELSE', 'LOOPS'],
        'stages': [
            {
                'title': 'Linux Survival Kit -- 7 Commands',
                'html': (
                    "You can't code in this unit without Linux. These 7 commands are your lightsabre:\n"
                    "  1. `pwd` -- where am I?\n"
                    "  2. `ls` -- list files. `ls -l` for details.\n"
                    "  3. `cd foldername` -- change directory. `cd ..` goes UP.\n"
                    "  4. `mkdir foldername` -- make new folder.\n"
                    "  5. `cp source dest` -- copy. `mv` -- move/rename.\n"
                    "  6. `rm file` -- delete. `rm -r folder` for folders.\n"
                    "  7. `vim file.py` -- open in vim.\n"
                    "\n"
                    "[TIP] Vim cheat: press `i` to INSERT, type your code, press `Esc`, then `:wq` "
                    "to save + quit. That's 90% of what you need."
                ),
            },
            {
                'title': 'hello.py -- Your First Python Program',
                'html': "Type this code, click RUN. You'll be asked for your name in a pop-up (that's Python's `input()` running live).",
                'code': {
                    'filename': 'hello.py',
                    'starter': (
                        '# hello.py - my first python program\n'
                        'print("Hello, Python Quest!")\n'
                        'name = input("What\'s your name? ")\n'
                        'print("G\'day,", name)'
                    ),
                },
                'afterHtml': (
                    "Decode each line:\n"
                    "  * `print(...)` sends text OUT to the screen.\n"
                    "  * `input(...)` stops & waits for the user to type something.\n"
                    "  * `name = input(...)` -- the `=` stores the typed value in a variable called `name`.\n"
                    "  * Text in \"quotes\" = a string. No quotes = a variable name.\n"
                    "\n"
                    "[WARN] `input()` always gives you a string. If you need a number, wrap it: "
                    "`age = int(input(\"Age? \"))`."
                ),
            },
            {
                'title': 'Arithmetic Operators -- Python Does Maths',
                'html': (
                    "Before we make decisions, you need the six arithmetic operators. "
                    "Type this in and run it. Watch ESPECIALLY what `//` and `%` do -- "
                    "they show up everywhere later.\n"
                    "\n"
                    "  * `+` add       * `-` subtract     * `*` multiply\n"
                    "  * `/` divide (always float)        * `**` power\n"
                    "  * `//` integer-divide (drops the remainder)\n"
                    "  * `%`  modulo  (JUST the remainder)"
                ),
                'code': {
                    'filename': 'maths.py',
                    'starter': (
                        '# maths.py - the six arithmetic operators\n'
                        'a = 17\n'
                        'b = 5\n'
                        '\n'
                        'print("a + b  =", a + b)     # 22\n'
                        'print("a - b  =", a - b)     # 12\n'
                        'print("a * b  =", a * b)     # 85\n'
                        'print("a / b  =", a / b)     # 3.4   (float!)\n'
                        'print("a // b =", a // b)    # 3     (integer divide)\n'
                        'print("a % b  =", a % b)     # 2     (the REMAINDER)\n'
                        'print("a ** 2 =", a ** 2)    # 289   (a to the power 2)\n'
                        '\n'
                        '# The classic use of %: is a number even or odd?\n'
                        'n = 8\n'
                        'print("8 % 2  =", 8 % 2)     # 0  -> even\n'
                        'print("7 % 2  =", 7 % 2)     # 1  -> odd\n'
                        '\n'
                        '# Remainders are everywhere: hours on a 12h clock, days of week, etc.\n'
                        'print("25 % 12 =", 25 % 12)  # 25 hours -> 1 oclock'
                    ),
                },
                'afterHtml': (
                    "[TIP] `%` is called **modulo**. It gives you the REMAINDER after a division.\n"
                    "  * `10 % 2` is `0`  (10 divides evenly by 2)\n"
                    "  * `10 % 3` is `1`  (10 / 3 is 3 remainder 1)\n"
                    "  * `n % 2 == 0` means \"n is even\"\n"
                    "\n"
                    "[WARN] Don't mix up `/` and `//`.  `7 / 2` gives `3.5`. `7 // 2` gives `3`. "
                    "If a function wants an integer (like `range()`), use `//`."
                ),
            },
            {
                'title': 'Decisions -- if / elif / else',
                'html': "Different code for different situations. Type a score and see what happens:",
                'code': {
                    'filename': 'grade.py',
                    'starter': (
                        '# grade.py - classify a score\n'
                        'score = int(input("Your score out of 100: "))\n'
                        '\n'
                        'if score >= 80:\n'
                        '    print("HD! ")\n'
                        'elif score >= 70:\n'
                        '    print("Distinction")\n'
                        'elif score >= 50:\n'
                        '    print("Pass")\n'
                        'else:\n'
                        '    print("Fail - try again")'
                    ),
                },
                'afterHtml': (
                    "[TIP] Python uses indentation (4 spaces) to show what's inside the `if`. No curly braces.\n"
                    "\n"
                    "Operators: `==` equals, `!=` not equals, `>` `<` `>=` `<=`. Combine with `and`, `or`, `not`.\n"
                    "\n"
                    "[WARN] `=` is assignment. `==` is comparison. Mixing these = classic bug."
                ),
            },
            {
                'title': 'Loops -- for and while',
                'html': "Repeat code. Two flavours. First, a `for` loop (when you know how many times):",
                'code': {
                    'filename': 'forloop.py',
                    'starter': (
                        '# forloop.py - sum 5 numbers from the user\n'
                        'total = 0\n'
                        'for i in range(5):\n'
                        '    n = int(input(f"Enter number {i + 1}: "))\n'
                        '    total = total + n\n'
                        'print("Total:", total)'
                    ),
                },
                'afterHtml': "And a `while` loop (when you don't know how many times, but you have a stop condition):",
                'code2': {
                    'filename': 'whileloop.py',
                    'starter': (
                        '# whileloop.py - keep asking until user types "quit"\n'
                        'answer = ""\n'
                        'count = 0\n'
                        'while answer != "quit":\n'
                        '    answer = input("Type anything (or \'quit\' to stop): ")\n'
                        '    count = count + 1\n'
                        'print("You said", count - 1, "things before quitting.")'
                    ),
                },
                'afterHtml2': "[QUEST] Modify the for-loop above to sum 10 numbers instead of 5. (Hint: change `range(5)`.)",
            },
        ],
        'quiz': {
            'q': "What will this print?\n\nfor i in range(3):\n    print(i * 2)",
            'options': ["0 2 4", "2 4 6", "0 1 2", "1 2 3"],
            'correct': 0,
            'explain': "range(3) gives 0, 1, 2. Each x 2 = 0, 2, 4. range starts at 0 and stops BEFORE the given number.",
        },
    },

    # ---------- LEVEL 2 ----------
    {
        'id': 2,
        'num': 'P2',
        'title': 'Strings & Lists -- The Collection Arsenal',
        'desc': 'Index, slice, split, join. The data-handling toolkit.',
        'xp': 45,
        'badges': ['STRINGS', 'LISTS', 'INDEXING', 'SLICING'],
        'stages': [
            {
                'title': 'Strings Are Sequences',
                'html': "A string is a sequence of characters. Each character has an index starting at 0. Negative indexes count from the end.",
                'code': {
                    'filename': 'indexing.py',
                    'starter': (
                        '# indexing.py - exploring string indexes\n'
                        'word = "PYTHON"\n'
                        '#         P Y T H O N\n'
                        '# index:  0 1 2 3 4 5\n'
                        '# neg:   -6-5-4-3-2-1\n'
                        '\n'
                        'print("First letter:", word[0])\n'
                        'print("Last letter:", word[-1])\n'
                        'print("Length:", len(word))\n'
                        'print("Slice 0-3:", word[0:3])    # PYT\n'
                        'print("Slice 2+:", word[2:])      # THON\n'
                        'print("Reversed:", word[::-1])'
                    ),
                },
                'afterHtml': "[TIP] Slicing `[start:end]` -- end is NOT included. `word[0:3]` gives you chars 0, 1, 2 (three chars).",
            },
            {
                'title': "String Methods You'll Use Daily",
                'html': "Strings have built-in skills. Call them with a dot:",
                'code': {
                    'filename': 'strmethods.py',
                    'starter': (
                        '# strmethods.py\n'
                        's = "  Hello World  "\n'
                        '\n'
                        'print(s.strip())            # removes outer whitespace\n'
                        'print(s.lower())            # all lowercase\n'
                        'print(s.upper())            # all uppercase\n'
                        'print(s.replace("Hello", "Hi"))\n'
                        "print(s.strip().split())    # ['Hello', 'World']\n"
                        '\n'
                        'csv = "apple,pear,lime"\n'
                        "print(csv.split(\",\"))       # ['apple', 'pear', 'lime']"
                    ),
                },
                'afterHtml': "[WARN] String methods return NEW strings -- they don't modify the original. `s.upper()` alone does nothing unless you do `s = s.upper()`.",
            },
            {
                'title': 'Lists -- Collections That Grow',
                'html': "Lists hold multiple items. Square brackets. Mutable (you can change them).",
                'code': {
                    'filename': 'lists.py',
                    'starter': (
                        '# lists.py\n'
                        'fruits = ["apple", "pear", "lime"]\n'
                        '\n'
                        'print("All fruits:", fruits)\n'
                        'print("First:", fruits[0])\n'
                        'print("Count:", len(fruits))\n'
                        '\n'
                        '# Modify the list\n'
                        'fruits.append("kiwi")       # add to end\n'
                        'fruits[0] = "mango"         # replace\n'
                        'fruits.remove("pear")       # remove by value\n'
                        '\n'
                        'print("After changes:", fruits)\n'
                        '\n'
                        '# Loop through\n'
                        'for fruit in fruits:\n'
                        '    print("I love", fruit)\n'
                        '\n'
                        '# Check membership\n'
                        'print("lime in list?", "lime" in fruits)'
                    ),
                },
                'afterHtml': "[QUEST] Add your own list of 5 subjects. Append a 6th. Loop through and print `\"I'm studying X\"` for each.",
            },
        ],
        'quiz': {
            'q': 'Given s = "programming", what does s[3:7] give?',
            'options': ['"gram"', '"gramm"', '"prog"', '"ramm"'],
            'correct': 0,
            'explain': "Start at index 3 ('g'), stop BEFORE index 7. That's chars 3, 4, 5, 6 -> 'g', 'r', 'a', 'm' = 'gram'.",
        },
    },

    # ---------- LEVEL 3 ----------
    {
        'id': 3,
        'num': 'P3',
        'title': 'Arrays & Plotting -- Data Gets Visual',
        'desc': 'numpy arrays for fast math. matplotlib for charts.',
        'xp': 50,
        'badges': ['NUMPY', 'MATPLOTLIB', 'ARRAYS'],
        'stages': [
            {
                'title': 'Why Arrays vs Lists?',
                'html': "Lists are flexible. numpy arrays are FAST and let you do math on all items at once.",
                'code': {
                    'filename': 'numpy_intro.py',
                    'starter': (
                        '# numpy_intro.py - the power of arrays\n'
                        'import numpy as np\n'
                        '\n'
                        'ages = np.array([18, 22, 19, 25, 30])\n'
                        '\n'
                        'print("Original:", ages)\n'
                        'print("Doubled:", ages * 2)       # whole array x 2!\n'
                        'print("Plus 1:", ages + 1)\n'
                        'print("Mean:", ages.mean())\n'
                        'print("Max:", ages.max())\n'
                        'print("Sum:", ages.sum())'
                    ),
                },
                'afterHtml': "Array creation shortcuts:",
                'code2': {
                    'filename': 'array_create.py',
                    'starter': (
                        'import numpy as np\n'
                        '\n'
                        'print(np.zeros(5))              # [0. 0. 0. 0. 0.]\n'
                        'print(np.ones(3))               # [1. 1. 1.]\n'
                        'print(np.arange(0, 10, 2))      # [0 2 4 6 8] - start, stop, step\n'
                        'print(np.linspace(0, 1, 5))     # 5 evenly spaced from 0 to 1'
                    ),
                },
            },
            {
                'title': 'Plotting -- The matplotlib Recipe',
                'html': (
                    "Import -> make data -> plot -> labels -> show. On desktop Python you'll "
                    "normally call `plt.show()` and a chart window opens.\n"
                    "\n"
                    "[WARN] If you run the full plt.show() inside this app it may freeze the window. "
                    "So we `matplotlib.use(\"Agg\")` and just COMPUTE the plot. Run it on your own "
                    "Linux/desktop for the real popup chart."
                ),
                'code': {
                    'filename': 'curve.py',
                    'starter': (
                        '# curve.py - a parabola\n'
                        'import numpy as np\n'
                        'import matplotlib\n'
                        'matplotlib.use("Agg")   # safe non-interactive backend\n'
                        'import matplotlib.pyplot as plt\n'
                        '\n'
                        'x = np.linspace(-5, 5, 50)\n'
                        'y = x ** 2\n'
                        '\n'
                        'plt.plot(x, y, color="red", marker="*")\n'
                        'plt.title("Basic Parabola")\n'
                        'plt.xlabel("x")\n'
                        'plt.ylabel("y = x^2")\n'
                        '\n'
                        'print("Computed", len(x), "points.")\n'
                        'print("x range:", x.min(), "to", x.max())\n'
                        'print("y range:", y.min(), "to", y.max())\n'
                        'print("On Linux/desktop, add plt.show() to see the actual chart!")'
                    ),
                },
                'afterHtml': "[QUEST] Change the code to plot a sine wave: `y = np.sin(x)`, with `x = np.linspace(0, 2*np.pi, 100)`.",
            },
        ],
        'quiz': {
            'q': "What's the main advantage of numpy arrays over lists for numerical work?",
            'options': [
                "They hold mixed types.",
                "Vectorised math -- you can do `arr * 2` instead of looping.",
                "They auto-sort.",
                "They're always 2D.",
            ],
            'correct': 1,
            'explain': "Arrays support element-wise operations on the whole array at once. Faster, shorter, cleaner code.",
        },
    },

    # ---------- LEVEL 4 ----------
    {
        'id': 4,
        'num': 'P4',
        'title': '2D Arrays & Functions -- Reusable Power',
        'desc': 'Define your own functions. Work with grids.',
        'xp': 55,
        'badges': ['FUNCTIONS', '2D ARRAYS', 'PARAMETERS'],
        'stages': [
            {
                'title': 'Functions -- Reusable Blocks',
                'html': "Define once (`def`), call many times. Functions take parameters and can return values.",
                'code': {
                    'filename': 'functions.py',
                    'starter': (
                        '# functions.py\n'
                        'def greet(name, greeting="G\'day"):\n'
                        '    """Greet a person."""\n'
                        '    print(greeting + ", " + name + "!")\n'
                        '\n'
                        'def square(n):\n'
                        '    """Return n squared."""\n'
                        '    return n * n\n'
                        '\n'
                        '# Calling\n'
                        'greet("Alex")\n'
                        'greet("Sam", "Howdy")\n'
                        '\n'
                        'result = square(7)\n'
                        'print("7 squared is", result)\n'
                        'print("9 squared is", square(9))'
                    ),
                },
                'afterHtml': "[WARN] `print` shows output. `return` hands a value BACK to the caller. If a function prints but doesn't return, trying to store its result gives you `None`.",
            },
            {
                'title': 'Mini-Quest: Write is_even()',
                'html': "Fill in the blank. The test code below will check your function works:",
                'code': {
                    'filename': 'is_even.py',
                    'starter': (
                        '# is_even.py\n'
                        'def is_even(n):\n'
                        '    # YOUR CODE HERE - return True if n is even, else False\n'
                        '    # Hint: use the % (modulo) operator\n'
                        '    pass    # <- delete this line and write your code\n'
                        '\n'
                        "# Test code (don't change this part)\n"
                        'print("0 is even?", is_even(0))    # expect True\n'
                        'print("3 is even?", is_even(3))    # expect False\n'
                        'print("8 is even?", is_even(8))    # expect True\n'
                        'print("-4 is even?", is_even(-4))  # expect True'
                    ),
                },
                'afterHtml': "[TIP] The answer is one line: `return n % 2 == 0`. The `%` operator gives the remainder after division. Even numbers have remainder 0 when divided by 2.",
            },
            {
                'title': '2D Arrays -- Grids',
                'html': "A 2D array is an array of arrays. Think: spreadsheet, image, game board.",
                'code': {
                    'filename': 'grid.py',
                    'starter': (
                        '# grid.py - 2D arrays\n'
                        'import numpy as np\n'
                        '\n'
                        'grid = np.zeros((3, 4))    # 3 rows, 4 columns of zeros\n'
                        'print("Empty grid:")\n'
                        'print(grid)\n'
                        'print("Shape:", grid.shape)\n'
                        '\n'
                        '# Set specific cells\n'
                        'grid[0, 0] = 1\n'
                        'grid[1, 2] = 99\n'
                        'grid[2, 3] = 7\n'
                        '\n'
                        'print("\\nAfter updates:")\n'
                        'print(grid)\n'
                        '\n'
                        '# Loop through every cell\n'
                        'print("\\nLooping through:")\n'
                        'for row in range(grid.shape[0]):\n'
                        '    for col in range(grid.shape[1]):\n'
                        '        print(f"  [{row},{col}] = {grid[row, col]}")'
                    ),
                },
                'afterHtml': "[TIP] Nested loop pattern: outer = rows, inner = cols. `grid.shape` gives you `(rows, cols)`.",
            },
        ],
        'quiz': {
            'q': "What's the difference between print() and return in a function?",
            'options': [
                "They're the same.",
                "print shows to the user; return hands a value back to the caller so it can be stored/used.",
                "return is only for numbers.",
                "print is faster.",
            ],
            'correct': 1,
            'explain': "print = output to screen. return = give value back to caller: `x = square(5)` works because square RETURNS 25. If it only printed, x would be None.",
        },
    },

    # ---------- LEVEL 5 ----------
    {
        'id': 5,
        'num': 'P5',
        'title': 'Files & Grids -- Making Data Persist',
        'desc': 'Read/write text files. List comprehensions. Grid simulations.',
        'xp': 60,
        'badges': ['FILES', 'LIST-COMP', 'SIMULATION'],
        'stages': [
            {
                'title': 'Writing a File',
                'html': "Python writes files with `open()`. The `with` statement auto-closes the file when done:",
                'code': {
                    'filename': 'filewrite.py',
                    'starter': (
                        '# filewrite.py\n'
                        "# The 'with' pattern auto-closes the file when done\n"
                        'with open("notes.txt", "w") as f:\n'
                        '    f.write("Hello from Python Quest!\\n")\n'
                        '    f.write("This is line two.\\n")\n'
                        '    f.write("File I/O is easy.\\n")\n'
                        '\n'
                        'print("File written.")\n'
                        '\n'
                        '# Check file size\n'
                        'import os\n'
                        'print("File size:", os.path.getsize("notes.txt"), "bytes")'
                    ),
                },
                'afterHtml': '[WARN] Mode `"w"` WIPES the old file. Use `"a"` (append) if you want to add without deleting.',
            },
            {
                'title': 'Reading a File',
                'html': "Three ways. Use whichever fits:",
                'code': {
                    'filename': 'fileread.py',
                    'starter': (
                        '# fileread.py - assumes notes.txt was made in previous stage\n'
                        '# Method 1: read the whole thing as one string\n'
                        'with open("notes.txt", "r") as f:\n'
                        '    content = f.read()\n'
                        'print("=== Method 1: read() ===")\n'
                        'print(content)\n'
                        '\n'
                        '# Method 2: line by line (best for big files)\n'
                        'print("=== Method 2: loop ===")\n'
                        'with open("notes.txt", "r") as f:\n'
                        '    for line in f:\n'
                        '        print(">", line.strip())\n'
                        '\n'
                        '# Method 3: all lines into a list\n'
                        'with open("notes.txt", "r") as f:\n'
                        '    lines = f.readlines()\n'
                        'print("=== Method 3: readlines() ===")\n'
                        'print("Got", len(lines), "lines")\n'
                        'print("Line 2 was:", lines[1].strip())'
                    ),
                },
                'afterHtml': "[TIP] `.strip()` removes the `\\n` (newline) at the end of each line.",
            },
            {
                'title': 'List Comprehensions',
                'html': "Build a list in one line: `[expression for item in sequence]`.",
                'code': {
                    'filename': 'listcomp.py',
                    'starter': (
                        '# listcomp.py\n'
                        '# Long way\n'
                        'squares_long = []\n'
                        'for i in range(8):\n'
                        '    squares_long.append(i * i)\n'
                        'print("Long way:", squares_long)\n'
                        '\n'
                        '# List comprehension - one line!\n'
                        'squares = [i * i for i in range(8)]\n'
                        'print("Comp:   ", squares)\n'
                        '\n'
                        '# With a filter\n'
                        'evens = [i for i in range(20) if i % 2 == 0]\n'
                        'print("Evens:  ", evens)\n'
                        '\n'
                        '# Transform strings\n'
                        'words = ["hello", "world", "python"]\n'
                        'upper = [w.upper() for w in words]\n'
                        'print("Upper:  ", upper)'
                    ),
                },
                'afterHtml': "[QUEST] Write a list comp that gives a list of the SQUARES of odd numbers from 1 to 20. Expected: [1, 9, 25, 49, 81, 121, 169, 225, 289, 361].",
            },
        ],
        'quiz': {
            'q': 'You open a file with open("log.txt", "w"). The file already existed with content. What happens?',
            'options': [
                "Content is appended to the end.",
                "Python raises an error.",
                "Old content is wiped and replaced.",
                "File is duplicated.",
            ],
            'correct': 2,
            'explain': 'Mode "w" = write from scratch. Previous content is DELETED. Use "a" (append) to add without deleting.',
        },
    },

    # ---------- LEVEL 6 -- PRIORITY ----------
    {
        'id': 6,
        'num': 'P6',
        'title': 'Objects -- Modelling the World [PRIORITY]',
        'desc': 'Classes, instances, __init__, self, methods. Heavy content. Take your time.',
        'xp': 90,
        'badges': ['CLASSES', '__init__', 'SELF', 'METHODS', '[TEST 4]'],
        'stages': [
            {
                'title': 'Why Classes? The Big Picture',
                'html': (
                    "Tracking shelter animals with parallel lists is chaos. A CLASS groups data + "
                    "behaviour into one unit.\n"
                    "\n"
                    "Class = blueprint. Object = one actual thing made from the blueprint. "
                    "\"Dog\" is a class. \"Rex\" is a Dog object (also called an instance)."
                ),
            },
            {
                'title': 'Your First Class -- Animal',
                'html': "Type this EXACT code. Run it. Then we'll break it down:",
                'code': {
                    'filename': 'animal.py',
                    'starter': (
                        '# animal.py - first class\n'
                        'class Animal():\n'
                        '    myclass = "Animal"   # class variable (shared by all)\n'
                        '\n'
                        '    def __init__(self, name, dob, colour, breed):\n'
                        '        # instance vars - unique per object\n'
                        '        self.name = name\n'
                        '        self.dob = dob\n'
                        '        self.colour = colour\n'
                        '        self.breed = breed\n'
                        '\n'
                        '    def printit(self):\n'
                        '        print(f"{self.myclass}: {self.name}, born {self.dob}, "\n'
                        '              f"{self.colour} {self.breed}")\n'
                        '\n'
                        '# Create (instantiate) two animals\n'
                        'rex = Animal("Rex", "1/1/20", "brown", "Labrador")\n'
                        'tweety = Animal("Tweety", "2/2/22", "yellow", "Canary")\n'
                        '\n'
                        'rex.printit()\n'
                        'tweety.printit()\n'
                        '\n'
                        '# Access instance variables directly\n'
                        'print("\\nDirect access:")\n'
                        'print("Rex\'s colour:", rex.colour)\n'
                        'print("Tweety\'s name:", tweety.name)'
                    ),
                },
                'afterHtml': (
                    "Breakdown -- memorise this:\n"
                    "  1. `class Animal():` -- defines a new type.\n"
                    "  2. `myclass = \"Animal\"` -- a class variable. Shared by every Animal.\n"
                    "  3. `def __init__(self, ...)` -- the constructor. Runs automatically when you do `Animal(...)`. `self` = the specific object being built.\n"
                    "  4. `self.name = name` -- stores this name INSIDE this specific object (instance variable).\n"
                    "  5. `def printit(self)` -- a method. First parameter is always `self`.\n"
                    "\n"
                    "[WARN] Every method's first parameter is `self`. You don't pass it in when calling "
                    "-- Python fills it automatically. Forgetting `self` = #1 beginner bug."
                ),
            },
            {
                'title': 'Class Variables vs Instance Variables -- CLASSIC TEST Q',
                'html': "This is almost guaranteed to be on Prac Test 4. Run this carefully and watch the output:",
                'code': {
                    'filename': 'classvar.py',
                    'starter': (
                        '# classvar.py - demonstrating the difference\n'
                        'class BankAccount:\n'
                        '    interest_rate = 0.05    # CLASS variable - SHARED\n'
                        '\n'
                        '    def __init__(self, owner, balance):\n'
                        '        self.owner = owner      # INSTANCE variable - unique\n'
                        '        self.balance = balance\n'
                        '\n'
                        '    def show(self):\n'
                        '        print(f"{self.owner}: ${self.balance}, rate={self.interest_rate}")\n'
                        '\n'
                        'a1 = BankAccount("Alice", 100)\n'
                        'a2 = BankAccount("Bob", 200)\n'
                        '\n'
                        'a1.show()\n'
                        'a2.show()\n'
                        '\n'
                        '# Now change the CLASS variable\n'
                        'BankAccount.interest_rate = 0.02\n'
                        'print("\\n--- After BankAccount.interest_rate = 0.02 ---")\n'
                        'a1.show()   # Alice now sees 0.02!\n'
                        'a2.show()   # Bob also sees 0.02!\n'
                        '# Because it\'s shared across ALL accounts.'
                    ),
                },
                'afterHtml': "[TIP] Class var = one copy, shared by all objects. Instance var = one copy per object. Change a class var -> every object sees the change instantly.",
            },
            {
                'title': 'Methods That Modify State Safely',
                'html': "Methods aren't just for printing. Use them to CHANGE object data safely, with validation:",
                'code': {
                    'filename': 'bankaccount.py',
                    'starter': (
                        '# bankaccount.py\n'
                        'class BankAccount:\n'
                        '    def __init__(self, owner, balance):\n'
                        '        self.owner = owner\n'
                        '        self.balance = balance\n'
                        '\n'
                        '    def deposit(self, amount):\n'
                        '        if amount > 0:\n'
                        '            self.balance += amount\n'
                        '            print(f"Deposited ${amount}. New balance: ${self.balance}")\n'
                        '        else:\n'
                        '            print("Deposit must be positive.")\n'
                        '\n'
                        '    def withdraw(self, amount):\n'
                        '        if amount <= 0:\n'
                        '            print("Withdraw must be positive.")\n'
                        '        elif amount > self.balance:\n'
                        '            print(f"Insufficient funds (you have ${self.balance})")\n'
                        '        else:\n'
                        '            self.balance -= amount\n'
                        '            print(f"Withdrew ${amount}. New balance: ${self.balance}")\n'
                        '\n'
                        '# Try it\n'
                        'acc = BankAccount("Sam", 500)\n'
                        'acc.deposit(200)\n'
                        'acc.withdraw(100)\n'
                        'acc.withdraw(9999)    # too much!\n'
                        'acc.deposit(-50)      # invalid'
                    ),
                },
                'afterHtml': (
                    "[BOSS] BUILD IT FROM SCRATCH. Open a new mental editor.\n"
                    "Write a Car class with `make`, `model`, `year`, `kms`. Methods: "
                    "`drive(distance)` adds to kms, `display()` prints everything. Create two "
                    "Cars and drive them different distances. This IS Prac Test 4 material."
                ),
                'code2': {
                    'filename': 'car_challenge.py',
                    'starter': (
                        '# car_challenge.py - YOUR TURN\n'
                        '# Build this WITHOUT looking at the BankAccount example if you can.\n'
                        '\n'
                        'class Car:\n'
                        '    def __init__(self, make, model, year):\n'
                        '        # YOUR CODE: store make, model, year, and kms (start at 0)\n'
                        '        pass\n'
                        '\n'
                        '    def drive(self, distance):\n'
                        '        # YOUR CODE: add distance to self.kms\n'
                        '        pass\n'
                        '\n'
                        '    def display(self):\n'
                        '        # YOUR CODE: print make, model, year, and kms\n'
                        '        pass\n'
                        '\n'
                        '# Test code\n'
                        'c1 = Car("Toyota", "Corolla", 2021)\n'
                        'c2 = Car("Honda", "Civic", 2023)\n'
                        '\n'
                        'c1.drive(150)\n'
                        'c1.drive(200)\n'
                        'c2.drive(80)\n'
                        '\n'
                        'c1.display()  # expect 350 km\n'
                        'c2.display()  # expect 80 km'
                    ),
                },
            },
        ],
        'quiz': {
            'q': "Inside a class, what does `self` refer to?",
            'options': [
                "The class itself (e.g. Animal).",
                "The specific object instance the method was called on.",
                "A built-in variable you can't rename.",
                "The main program.",
            ],
            'correct': 1,
            'explain': "self is the SPECIFIC object. When you write `rex.printit()`, inside printit self = rex. Call `tweety.printit()` -> self = tweety. One method, many instances.",
        },
    },

    # ---------- LEVEL 7 -- PRIORITY ----------
    {
        'id': 7,
        'num': 'P7',
        'title': 'Inheritance & Exceptions [PRIORITY]',
        'desc': 'Subclasses, super(), IS-A vs HAS-A, try/except. THE Prac Test 4 content.',
        'xp': 100,
        'badges': ['INHERITANCE', 'super()', 'TRY/EXCEPT', '[TEST 4]'],
        'stages': [
            {
                'title': 'Three Class Relationships -- Memorise',
                'html': (
                    "Prac Test 4 loves this. Know these cold:\n"
                    "  1. Inheritance (IS-A) -- A Dog IS AN Animal. Subclass extends parent.\n"
                    "  2. Composition (HAS-A, strong) -- A Person HAS AN Address. Address lives and dies with Person.\n"
                    "  3. Aggregation (HAS-A, weak) -- A Shelter HAS Animals. Animals exist even if shelter closes.\n"
                    "\n"
                    "[TIP] Litmus test: destroy the container. Are the contents still meaningful alone? "
                    "Yes -> aggregation. No -> composition."
                ),
            },
            {
                'title': 'Inheritance -- Person and Staff',
                'html': "Don't repeat code. Extend it. Staff IS A Person with an extra field (ID). This is straight from Prac 7.",
                'code': {
                    'filename': 'people.py',
                    'starter': (
                        '# people.py - inheritance example\n'
                        'class Person():\n'
                        '    def __init__(self, name, dob, address):\n'
                        '        self.name = name\n'
                        '        self.dob = dob\n'
                        '        self.address = address\n'
                        '\n'
                        '    def displayPerson(self):\n'
                        '        print("Name:", self.name, "  DOB:", self.dob)\n'
                        '        print("  Address:", self.address)\n'
                        '\n'
                        '\n'
                        'class Staff(Person):       # Staff extends Person\n'
                        '    myclass = "Staff"\n'
                        '\n'
                        '    def __init__(self, name, dob, address, id):\n'
                        "        super().__init__(name, dob, address)   # call parent's __init__\n"
                        '        self.id = id                            # add new field\n'
                        '\n'
                        '    def displayPerson(self):\n'
                        "        super().displayPerson()                 # parent's logic first\n"
                        '        print("  Staff ID:", self.id)           # then add our bit\n'
                        '\n'
                        '\n'
                        '# Test it\n'
                        'p1 = Person("Winston Churchill", "30/11/1874", "10 Downing St")\n'
                        'p1.displayPerson()\n'
                        '\n'
                        'print()\n'
                        '\n'
                        'p2 = Staff("Prof Awesome", "1/6/61", "1 Infinite Loop", "12345J")\n'
                        'p2.displayPerson()'
                    ),
                },
                'afterHtml': (
                    "Decode:\n"
                    "  * `class Staff(Person):` -- Staff inherits from Person. Gets all Person's methods + fields for free.\n"
                    "  * `super().__init__(name, dob, address)` -- \"Do Person's __init__ first, then add my extras.\"\n"
                    "  * `super().displayPerson()` -- \"Run Person's version, then add my extra print.\"\n"
                    "\n"
                    "[WARN] If you skip `super().__init__()` in the child, parent fields are never set "
                    "and you'll get AttributeError."
                ),
            },
            {
                'title': 'The Full People Hierarchy (Prac 7 verbatim)',
                'html': "Person -> Student -> {Postgrad, Undergrad}. And Person -> Staff. Note how Postgrad/Undergrad inherit everything from Student without rewriting anything.",
                'code': {
                    'filename': 'hierarchy.py',
                    'starter': (
                        '# hierarchy.py - multi-level inheritance\n'
                        'class Person():\n'
                        '    myclass = "Person"\n'
                        '    def __init__(self, name, dob):\n'
                        '        self.name = name\n'
                        '        self.dob = dob\n'
                        '    def displayPerson(self):\n'
                        '        print(f"[{self.myclass}] {self.name} (DOB {self.dob})")\n'
                        '\n'
                        '\n'
                        'class Student(Person):\n'
                        '    myclass = "Student"\n'
                        '    def __init__(self, name, dob, student_id):\n'
                        '        super().__init__(name, dob)\n'
                        '        self.student_id = student_id\n'
                        '    def displayPerson(self):\n'
                        '        super().displayPerson()\n'
                        '        print(f"  Student ID: {self.student_id}")\n'
                        '\n'
                        '\n'
                        'class Postgrad(Student):\n'
                        '    myclass = "Postgrad"\n'
                        '    # Inherits EVERYTHING from Student. No need to write __init__!\n'
                        '\n'
                        '\n'
                        'class Undergrad(Student):\n'
                        '    myclass = "Undergrad"\n'
                        '\n'
                        '\n'
                        'class Staff(Person):\n'
                        '    myclass = "Staff"\n'
                        '    def __init__(self, name, dob, staff_id):\n'
                        '        super().__init__(name, dob)\n'
                        '        self.staff_id = staff_id\n'
                        '    def displayPerson(self):\n'
                        '        super().displayPerson()\n'
                        '        print(f"  Staff ID: {self.staff_id}")\n'
                        '\n'
                        '\n'
                        '# Test\n'
                        'people = [\n'
                        '    Undergrad("Alex Uni", "2003-05-01", "U12345"),\n'
                        '    Postgrad("Sam PhD",   "1998-11-11", "P99999"),\n'
                        '    Staff("Dr Smith",     "1975-03-20", "S00001"),\n'
                        ']\n'
                        '\n'
                        'for p in people:\n'
                        '    p.displayPerson()\n'
                        '    print()'
                    ),
                },
                'afterHtml': "[TIP] Postgrad and Undergrad don't even define `__init__` -- they get Student's for free. They just override `myclass`. Clean.",
            },
            {
                'title': 'Exception Handling -- try / except',
                'html': "Code that MIGHT fail goes in `try`. Plan B goes in `except`.",
                'code': {
                    'filename': 'tryexcept.py',
                    'starter': (
                        '# tryexcept.py\n'
                        '# Try 1: a bad int conversion (type "abc" when asked)\n'
                        'try:\n'
                        '    age = int(input("Your age? "))\n'
                        '    print("You are", age, "years old")\n'
                        'except ValueError:\n'
                        "    print(\"That wasn't a number. Setting age to 0.\")\n"
                        '    age = 0\n'
                        '\n'
                        'print("Final age:", age)\n'
                        'print()\n'
                        '\n'
                        "# Try 2: file that doesn't exist\n"
                        'try:\n'
                        '    with open("doesnotexist.txt", "r") as f:\n'
                        '        data = f.read()\n'
                        '    print("File contents:", data)\n'
                        'except FileNotFoundError:\n'
                        '    print("File not found. Creating an empty one.")\n'
                        '    data = ""\n'
                        '\n'
                        '# Try 3: list index out of range\n'
                        'my_list = [1, 2, 3]\n'
                        'try:\n'
                        '    print(my_list[99])\n'
                        'except IndexError:\n'
                        '    print("Index 99 is out of range for a list of", len(my_list))\n'
                        '\n'
                        '# Try 4: divide by zero\n'
                        'try:\n'
                        '    x = 10 / 0\n'
                        'except ZeroDivisionError:\n'
                        "    print(\"Can't divide by zero!\")"
                    ),
                },
                'afterHtml': (
                    "Common exceptions to know:\n"
                    "  * ValueError -- wrong value (e.g. `int(\"hello\")`)\n"
                    "  * FileNotFoundError -- file doesn't exist\n"
                    "  * IndexError -- list[99] when list has 3 items\n"
                    "  * KeyError -- dict missing a key\n"
                    "  * ZeroDivisionError -- divide by 0"
                ),
            },
            {
                'title': 'The Full Pattern -- try/except/else/finally',
                'html': "Sometimes you need all four clauses:",
                'code': {
                    'filename': 'fullexcept.py',
                    'starter': (
                        '# fullexcept.py\n'
                        'def safe_divide(a, b):\n'
                        '    try:\n'
                        '        result = a / b\n'
                        '    except ZeroDivisionError:\n'
                        "        print(f\"  Can't divide {a} by 0\")\n"
                        '        return None\n'
                        '    except TypeError:\n'
                        '        print(f"  Bad types: {a} / {b}")\n'
                        '        return None\n'
                        '    else:\n'
                        '        # runs ONLY if try succeeded\n'
                        '        print(f"  {a} / {b} = {result}")\n'
                        '        return result\n'
                        '    finally:\n'
                        '        # runs ALWAYS - even if exception raised\n'
                        '        print("  (cleanup done)")\n'
                        '\n'
                        'safe_divide(10, 2)\n'
                        'print()\n'
                        'safe_divide(10, 0)\n'
                        'print()\n'
                        'safe_divide(10, "x")'
                    ),
                },
                'afterHtml': (
                    "[BOSS] PRAC TEST 4 BOSS CHALLENGE.\n"
                    "Build a Vehicle -> Car + Motorbike hierarchy:\n"
                    "  1. Vehicle has: make, model, year.\n"
                    "  2. Car adds: num_doors.\n"
                    "  3. Motorbike adds: engine_cc.\n"
                    "  4. All have a display() method; subclasses use super().\n"
                    "  5. Wrap the input of year in a try/except that catches ValueError.\n"
                    "\n"
                    "If you can build this in <= 15 min without peeking -> you're test-ready."
                ),
                'code2': {
                    'filename': 'boss_vehicle.py',
                    'starter': (
                        '# boss_vehicle.py - YOUR CHALLENGE\n'
                        '# Build the Vehicle hierarchy. Starter scaffold below.\n'
                        '\n'
                        'class Vehicle:\n'
                        '    def __init__(self, make, model, year):\n'
                        '        # YOUR CODE\n'
                        '        pass\n'
                        '    def display(self):\n'
                        '        # YOUR CODE\n'
                        '        pass\n'
                        '\n'
                        'class Car(Vehicle):\n'
                        '    def __init__(self, make, model, year, num_doors):\n'
                        '        # call super().__init__() then add num_doors\n'
                        '        pass\n'
                        '    def display(self):\n'
                        '        # call super().display() then add door count\n'
                        '        pass\n'
                        '\n'
                        'class Motorbike(Vehicle):\n'
                        '    def __init__(self, make, model, year, engine_cc):\n'
                        '        pass\n'
                        '    def display(self):\n'
                        '        pass\n'
                        '\n'
                        '# Test with try/except on year input\n'
                        'try:\n'
                        '    year_str = input("Car year? ")\n'
                        '    year = int(year_str)\n'
                        '    c = Car("Toyota", "Corolla", year, 4)\n'
                        '    c.display()\n'
                        'except ValueError:\n'
                        '    print("Year must be a number!")'
                    ),
                },
            },
        ],
        'quiz': {
            'q': "Inside a subclass, what does super().__init__(name, dob) do?",
            'options': [
                "Creates a new parent object with those values.",
                "Runs the parent's __init__ method on THIS object, so parent's fields get set up.",
                "Renames the class.",
                "Deletes the parent class.",
            ],
            'correct': 1,
            'explain': "super() gives you the parent class. super().__init__(...) runs the parent's init on self (this object), so all parent fields get initialised. Then you add subclass-specific fields after.",
        },
    },

    # ---------- LEVEL 8 ----------
    {
        'id': 8,
        'num': 'P8',
        'title': 'Scripts & Automation',
        'desc': 'Command-line args with sys.argv. Automate experiments.',
        'xp': 70,
        'badges': ['sys.argv', 'AUTOMATION', 'BASH'],
        'stages': [
            {
                'title': 'Command-Line Arguments',
                'html': "Make your Python script accept values when you run it. Here we'll simulate `sys.argv`:",
                'code': {
                    'filename': 'argv.py',
                    'starter': (
                        '# argv.py - accepting command-line arguments\n'
                        'import sys\n'
                        '\n'
                        '# Simulate: python3 myprog.py 42 hello\n'
                        "# In real Linux: sys.argv = ['myprog.py', '42', 'hello']\n'"
                        '# Here we fake it by setting sys.argv:\n'
                        "sys.argv = ['myprog.py', '42', 'hello']\n"
                        '\n'
                        'print("Script name:", sys.argv[0])\n'
                        'print("Total args:", len(sys.argv))\n'
                        '\n'
                        'if len(sys.argv) < 2:\n'
                        '    print("Usage: python3 myprog.py <number>")\n'
                        '    sys.exit()\n'
                        '\n'
                        '# cast - argv items are strings!\n'
                        'n = int(sys.argv[1])\n'
                        'message = sys.argv[2]\n'
                        '\n'
                        'print(f"Running with n={n}, msg=\'{message}\'")\n'
                        'for i in range(n):\n'
                        '    print(f"  {i}: {message}")'
                    ),
                },
                'afterHtml': (
                    "[WARN] `sys.argv[0]` is ALWAYS the script name. User args start at index `1`. "
                    "Everything in sys.argv is a string -- cast to int/float as needed.\n"
                    "\n"
                    "[TIP] On real Linux: `python3 argv.py 3 Boom` runs it. No faking."
                ),
            },
            {
                'title': 'Parameter Sweep -- The Automation Pattern',
                'html': "Run your simulation multiple times with different values. Log each result. This is the bread and butter of scientific computing.",
                'code': {
                    'filename': 'sweep.py',
                    'starter': (
                        '# sweep.py - parameter sweep pattern\n'
                        'import random\n'
                        '# reproducible "random" results\n'
                        'random.seed(42)\n'
                        '\n'
                        'def simulate(population, transmission_rate):\n'
                        '    """Tiny pretend disease model - returns infected count."""\n'
                        '    infected = 1\n'
                        '    for day in range(30):\n'
                        '        new = int(infected * transmission_rate)\n'
                        '        infected = min(population, infected + new)\n'
                        '    return infected\n'
                        '\n'
                        '# Sweep across multiple parameter values\n'
                        'pop = 1000\n'
                        'rates = [0.05, 0.1, 0.15, 0.2, 0.25]\n'
                        '\n'
                        "print(f\"{'Rate':<8}{'Infected':<12}\")\n"
                        'print("-" * 20)\n'
                        'for r in rates:\n'
                        '    result = simulate(pop, r)\n'
                        '    print(f"{r:<8}{result:<12}")\n'
                        '\n'
                        '# Save results to a file\n'
                        'with open("sweep_results.csv", "w") as f:\n'
                        '    f.write("rate,infected\\n")\n'
                        '    for r in rates:\n'
                        '        f.write(f"{r},{simulate(pop, r)}\\n")\n'
                        'print("\\nResults saved to sweep_results.csv")'
                    ),
                },
                'afterHtml': (
                    "On real Linux, you'd pair this with a bash script like:\n"
                    "\n"
                    "```\n"
                    "#!/bin/bash\n"
                    "for rate in 0.05 0.1 0.15 0.2 0.25\n"
                    "do\n"
                    "  python3 sim.py $rate\n"
                    "done\n"
                    "```"
                ),
            },
        ],
        'quiz': {
            'q': "Running `python3 myprog.py hello 42`, what does sys.argv[0] contain?",
            'options': ["'hello'", "'42'", "'myprog.py' (the script name)", "An empty string"],
            'correct': 2,
            'explain': "sys.argv[0] is always the script filename. User args start at index 1: [0]='myprog.py', [1]='hello', [2]='42'.",
        },
    },

    # ---------- LEVEL 9 ----------
    {
        'id': 9,
        'num': 'P9',
        'title': 'Quality & Testing',
        'desc': 'Code quality, testing, fixing broken code, choosing packages.',
        'xp': 60,
        'badges': ['TESTING', 'ASSERT', 'DEBUG'],
        'stages': [
            {
                'title': 'assert -- The One-Liner Test',
                'html': "`assert` says \"this better be true, or crash loudly.\" Perfect for quick sanity checks.",
                'code': {
                    'filename': 'assert_demo.py',
                    'starter': (
                        '# assert_demo.py\n'
                        'def add(a, b):\n'
                        '    return a + b\n'
                        '\n'
                        'def divide(a, b):\n'
                        "    assert b != 0, \"Can't divide by zero!\"\n"
                        '    return a / b\n'
                        '\n'
                        '# These should all pass silently\n'
                        'assert add(2, 3) == 5\n'
                        'assert add(-1, 1) == 0\n'
                        'assert add(0, 0) == 0\n'
                        'print("All add() tests passed")\n'
                        '\n'
                        'assert divide(10, 2) == 5\n'
                        'assert divide(9, 3) == 3\n'
                        'print("All divide() tests passed")\n'
                        '\n'
                        '# This one will fail - uncomment to see\n'
                        '# assert add(2, 2) == 5, "This is deliberately wrong"\n'
                        '\n'
                        '# Triggering the custom message\n'
                        'try:\n'
                        '    divide(10, 0)\n'
                        'except AssertionError as e:\n'
                        '    print("Caught expected error:", e)'
                    ),
                },
                'afterHtml': '[TIP] `assert condition, "message"`. If condition is False, you get AssertionError with your message. Perfect for catching bugs early.',
            },
            {
                'title': 'Fix The Broken Code -- Prac 9 Challenge',
                'html': "Prac 9 starts with buggy code you have to fix. Same style below -- find and fix the bugs:",
                'code': {
                    'filename': 'fixme.py',
                    'starter': (
                        '# fixme.py - spot and fix 3 bugs\n'
                        '# Expected output:\n'
                        '#   Hello, my name is Tim the Enchanter.\n'
                        '#   ******** (8 stars, because 898 // 100 = 8)\n'
                        '\n'
                        'myname = "Tim the Enchanter"\n'
                        'myyear = 898\n'
                        '\n'
                        'print(f"Hello, my name is {myname}.")\n'
                        'for i in range(myyear/100):       # BUG 1: should be //\n'
                        '    if i % 10 = 0:                # BUG 2: should be ==\n'
                        '        print("*", end="")\n'
                        '    print()                       # BUG 3: indented too far?\n'
                        "# The last 'print()' should be OUTSIDE the loop\n"
                        '# to put a newline at the very end.\n'
                        '\n'
                        '# Your job: fix the 3 bugs so it prints 8 stars then a newline.'
                    ),
                },
                'afterHtml': "[TIP] The `/` gives a float (like 8.98). `range()` needs an int, so use `//` (integer division).",
            },
            {
                'title': 'PyPI -- Picking Safe Packages',
                'html': (
                    "PyPI (Python Package Index, pypi.org) has 500k+ packages. Not all are good. When choosing:\n"
                    "  * Version >= 1.0 (pre-1.0 is unstable)\n"
                    "  * Recently updated (weeks, not years)\n"
                    "  * Many contributors > one person\n"
                    "  * Issues being closed (active maintenance)\n"
                    "  * Not buried in dependencies\n"
                    "\n"
                    "Install with: `pip install packagename` in terminal."
                ),
            },
        ],
        'quiz': {
            'q': "Which of these is the BEST signal a PyPI package is safe to depend on?",
            'options': [
                "It has a cool logo.",
                "Version 0.2.1, last updated 3 years ago.",
                "Version 2.5, updated last week, 40+ contributors, active issue tracking.",
                "It's mentioned in one tutorial.",
            ],
            'correct': 2,
            'explain': "Stable version number (>=1.0), recent activity, multiple contributors, and responsive issue-handling all indicate a well-maintained, trustworthy package.",
        },
    },

    # ---------- LEVEL 10 ----------
    {
        'id': 10,
        'num': 'P10',
        'title': 'Data Processing & Analytics',
        'desc': 'Real data pipeline: read -> clean -> analyse -> report.',
        'xp': 65,
        'badges': ['CSV', 'AGGREGATE', 'PIPELINE'],
        'stages': [
            {
                'title': 'The Data Pipeline',
                'html': "A typical data script: (1) read file, (2) parse/clean, (3) compute stats, (4) output. Let's do all four.",
                'code': {
                    'filename': 'pipeline.py',
                    'starter': (
                        '# pipeline.py - full data pipeline\n'
                        '# Step 1: create some sample data (in real life this is a CSV download)\n'
                        'data = """name,subject,score\n'
                        'Alex,Python,85\n'
                        'Sam,Python,72\n'
                        'Alex,Math,90\n'
                        'Sam,Math,68\n'
                        'Jo,Python,95\n'
                        'Jo,Math,88\n'
                        'Alex,Physics,79\n'
                        '"""\n'
                        'with open("scores.csv", "w") as f:\n'
                        '    f.write(data)\n'
                        '\n'
                        '# Step 2: read and parse\n'
                        'records = []\n'
                        'with open("scores.csv", "r") as f:\n'
                        '    # first line is header\n'
                        '    header = f.readline().strip().split(",")\n'
                        '    for line in f:\n'
                        '        parts = line.strip().split(",")\n'
                        "        if len(parts) < 3: continue\n"
                        '        record = {\n'
                        '            "name":    parts[0],\n'
                        '            "subject": parts[1],\n'
                        '            "score":   int(parts[2]),\n'
                        '        }\n'
                        '        records.append(record)\n'
                        '\n'
                        'print(f"Loaded {len(records)} records")\n'
                        '\n'
                        '# Step 3: analyse - average per student\n'
                        'totals = {}\n'
                        'counts = {}\n'
                        'for r in records:\n'
                        '    totals[r["name"]] = totals.get(r["name"], 0) + r["score"]\n'
                        '    counts[r["name"]] = counts.get(r["name"], 0) + 1\n'
                        '\n'
                        'print("\\nAverage score per student:")\n'
                        'for name in totals:\n'
                        '    avg = totals[name] / counts[name]\n'
                        '    print(f"  {name}: {avg:.1f}")\n'
                        '\n'
                        '# Step 4: find the top scorer\n'
                        'top = max(records, key=lambda r: r["score"])\n'
                        'print(f"\\nTop score: {top[\'name\']} got {top[\'score\']} in {top[\'subject\']}")'
                    ),
                },
                'afterHtml': (
                    "[TIP] `dict.get(key, default)` returns `default` if the key isn't there -- avoids KeyError.\n"
                    "\n"
                    "[QUEST] Add a 4th step: find the average score per SUBJECT (not per student). "
                    "Expected: Python avg ~ 84, Math avg ~ 82, Physics = 79."
                ),
            },
        ],
        'quiz': {
            'q': "In the pipeline code, why do we use `int(parts[2])` when reading the score?",
            'options': [
                "To speed up the code.",
                "Because split() always returns strings -- we need a number to do math.",
                "Because CSV files are binary.",
                "To save memory.",
            ],
            'correct': 1,
            'explain': 'split() returns a list of strings. "85" and 85 are different -- you can\'t do math on strings. int() converts for the aggregation step.',
        },
    },

    # ---------- LEVEL 11 ----------
    {
        'id': 11,
        'num': 'P11',
        'title': 'Applications in the Real World',
        'desc': 'Where coding takes you: GIS, space, health, physics. The closer.',
        'xp': 45,
        'badges': ['SIMULATION', 'APPLIED'],
        'stages': [
            {
                'title': 'A Real Applied Example -- Projectile Motion',
                'html': "Physics in Python. Where coding meets engineering. This is the kind of thing Prac 11's guest lecturers use daily.",
                'code': {
                    'filename': 'projectile.py',
                    'starter': (
                        '# projectile.py - physics simulation\n'
                        'import math\n'
                        '\n'
                        'def projectile(v0, angle_deg, g=9.81):\n'
                        '    """Given launch speed & angle, return time of flight, max height, range."""\n'
                        '    theta = math.radians(angle_deg)\n'
                        '    vy = v0 * math.sin(theta)\n'
                        '    vx = v0 * math.cos(theta)\n'
                        '\n'
                        '    t_flight = 2 * vy / g\n'
                        '    h_max = vy * vy / (2 * g)\n'
                        '    r_max = vx * t_flight\n'
                        '\n'
                        '    return t_flight, h_max, r_max\n'
                        '\n'
                        '# Test at several angles\n'
                        'v0 = 50    # m/s\n'
                        'print(f"Launching at {v0} m/s:\\n")\n'
                        "print(f\"{'Angle':<8}{'Flight(s)':<12}{'Height(m)':<12}{'Range(m)':<10}\")\n"
                        'print("-" * 42)\n'
                        '\n'
                        'best_angle = 0\n'
                        'best_range = 0\n'
                        'for angle in [15, 30, 45, 60, 75]:\n'
                        '    t, h, r = projectile(v0, angle)\n'
                        '    print(f"{angle:<8}{t:<12.2f}{h:<12.2f}{r:<10.2f}")\n'
                        '    if r > best_range:\n'
                        '        best_range = r\n'
                        '        best_angle = angle\n'
                        '\n'
                        'print(f"\\nBest angle for max range: {best_angle} deg -> {best_range:.1f}m")'
                    ),
                },
                'afterHtml': "[TIP] 45 deg always gives max range for ideal projectile motion (no air resistance). You just proved it computationally.",
            },
            {
                'title': "What's Next",
                'html': (
                    "You've done the unit. Where do the skills go?\n"
                    "  * Data science -- pandas, matplotlib, scikit-learn on real datasets.\n"
                    "  * Engineering -- simulations, control systems, signal processing.\n"
                    "  * Space/GIS -- like Prac 11's guest lecturers: satellite data, mapping.\n"
                    "  * Bio/chem -- molecular simulations, analysing lab data.\n"
                    "  * Software dev -- web (Django/Flask), mobile, systems.\n"
                    "\n"
                    "The unit is called Fundamentals of Programming. You now have the fundamentals. "
                    "Pick what excites you and build something."
                ),
            },
        ],
        'quiz': {
            'q': "At what angle does an ideal projectile travel furthest (no air resistance)?",
            'options': ["30 deg", "45 deg", "60 deg", "90 deg"],
            'correct': 1,
            'explain': "45 deg balances horizontal velocity (wants low angle) against airtime (wants high angle). Easy to prove computationally -- as you just did!",
        },
    },
]

# =============================================================================
#  STAGE CHALLENGES  (NEW FEATURE)
# -----------------------------------------------------------------------------
#  At the end of each Stage, the game randomly picks ONE of these challenges
#  from the level's bank. The student types code into a fresh editor and
#  clicks CHECK -- the output is compared against `expected_contains` (every
#  string must appear) or `expected_exact` (whole output must match after
#  trimming).
#
#  Each level gets 5 challenges. They focus on the level's topic so the
#  random pick is always relevant.
# =============================================================================
STAGE_CHALLENGES = {
    # ---------- LEVEL 1 :: Linux + Python Basics ----------
    # Stage map:  0=Linux  1=hello.py(print/input)  2=Arithmetic(+,-,*,/,//,%)
    #             3=if/elif/else  4=for/while loops
    1: [
        {
            'task': 'GREET YOURSELF',
            'desc': ('Write a program that prints two lines:\n'
                     "  1) The text:  Hello, World!\n"
                     "  2) The text:  My name is Coder."),
            'starter': '# Type your code here\n',
            'expected_contains': ['Hello, World!', 'My name is Coder'],
            'hint': 'Use print() twice. e.g.  print("Hello, World!")',
            'requires_stage': 1,   # needs: print()
        },
        {
            'task': 'AGE IN 10 YEARS',
            'desc': ('Set a variable `age` to 20.\n'
                     'Print exactly:   In 10 years I will be 30'),
            'starter': '# Type your code here\nage = 20\n',
            'expected_contains': ['In 10 years I will be 30'],
            'hint': 'Use:  print("In 10 years I will be", age + 10)',
            'requires_stage': 2,   # needs: variables + arithmetic (+)
        },
        {
            'task': 'PASS OR FAIL',
            'desc': ('Set a variable `score = 65`.\n'
                     'Use an if/else to print "Pass" if score >= 50, else "Fail".'),
            'starter': '# Type your code here\nscore = 65\n',
            'expected_contains': ['Pass'],
            'hint': 'if score >= 50:\n    print("Pass")\nelse:\n    print("Fail")',
            'requires_stage': 3,   # needs: if/else
        },
        {
            'task': 'COUNT TO FIVE',
            'desc': ('Use a for loop with range() to print numbers 1 through 5,\n'
                     'each on its own line.'),
            'starter': '# Type your code here\n',
            'expected_contains': ['1', '2', '3', '4', '5'],
            'hint': 'for i in range(1, 6):\n    print(i)',
            'requires_stage': 4,   # needs: for loop + range()
        },
        {
            'task': 'EVEN OR ODD',
            'desc': ('Set a variable `n = 7`.\n'
                     'Print "Even" if n is even, "Odd" otherwise.\n'
                     'For n = 7 you should see:   Odd'),
            'starter': '# Type your code here\nn = 7\n',
            'expected_contains': ['Odd'],
            'hint': 'Use the modulo operator:  if n % 2 == 0:',
            'requires_stage': 3,   # needs: modulo (stage 2) + if/else (stage 3)
        },
    ],

    # ---------- LEVEL 2 :: Strings & Lists ----------
    # Stage map:  0=Strings Are Sequences (index/slice)
    #             1=String Methods (upper/lower/split/replace)
    #             2=Lists (append/index/loop)
    2: [
        {
            'task': 'FIRST AND LAST',
            'desc': ('Set  word = "PYTHON".\n'
                     'Print the first letter on one line and the last letter on the next.'),
            'starter': '# Type your code here\nword = "PYTHON"\n',
            'expected_contains': ['P', 'N'],
            'hint': 'word[0] is the first letter. word[-1] is the last.',
            'requires_stage': 0,   # needs: string indexing
        },
        {
            'task': 'SHOUT IT',
            'desc': ('Set  msg = "hello world".\n'
                     'Print the message in ALL UPPERCASE.\n'
                     'Expected output:   HELLO WORLD'),
            'starter': '# Type your code here\nmsg = "hello world"\n',
            'expected_contains': ['HELLO WORLD'],
            'hint': 'Strings have a .upper() method.',
            'requires_stage': 1,   # needs: .upper()
        },
        {
            'task': 'SLICE IT',
            'desc': ('Set  s = "programming".\n'
                     'Print the slice from index 3 to index 7.\n'
                     'Expected output:   gram'),
            'starter': '# Type your code here\ns = "programming"\n',
            'expected_contains': ['gram'],
            'hint': 'Use s[3:7]. The end index is NOT included.',
            'requires_stage': 0,   # needs: slicing
        },
        {
            'task': 'BUILD A SHOPPING LIST',
            'desc': ('Create a list with these 3 items: "milk", "bread", "eggs".\n'
                     'Append "butter" to the list.\n'
                     'Print the final list.'),
            'starter': '# Type your code here\n',
            'expected_contains': ['milk', 'bread', 'eggs', 'butter'],
            'hint': 'items = ["milk", "bread", "eggs"]\nitems.append("butter")\nprint(items)',
            'requires_stage': 2,   # needs: lists + append
        },
        {
            'task': 'SPLIT THE CSV',
            'desc': ('Set  csv = "red,green,blue".\n'
                     'Split it on commas and print the resulting list.\n'
                     "Expected output:   ['red', 'green', 'blue']"),
            'starter': '# Type your code here\ncsv = "red,green,blue"\n',
            'expected_contains': ['red', 'green', 'blue'],
            'hint': 'Use csv.split(",")',
            'requires_stage': 1,   # needs: .split()
        },
    ],

    # ---------- LEVEL 3 :: Arrays & Plotting ----------
    # Stage map:  0=numpy arrays (array/sum/mean/max/zeros/arange/linspace)
    #             1=matplotlib plotting
    3: [
        {
            'task': 'SUM AN ARRAY',
            'desc': ('Use numpy to make an array of [10, 20, 30, 40, 50].\n'
                     'Print the sum.\n'
                     'Expected output:   150'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['150'],
            'hint': 'arr = np.array([10,20,30,40,50])\nprint(arr.sum())',
            'requires_stage': 0,
        },
        {
            'task': 'DOUBLE IT',
            'desc': ('Make a numpy array of [1, 2, 3, 4].\n'
                     'Multiply EVERY element by 2 in one expression.\n'
                     'Print the new array.   Expected: [2 4 6 8]'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['2', '4', '6', '8'],
            'hint': 'arr * 2 doubles every element at once.',
            'requires_stage': 0,
        },
        {
            'task': 'AVERAGE GRADE',
            'desc': ('Make a numpy array of marks: [55, 72, 89, 90, 64].\n'
                     'Print the mean to 1 decimal place.\n'
                     'Expected output:   74.0'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['74'],
            'hint': 'arr.mean() gives the average. Use f-string: f"{arr.mean():.1f}"',
            'requires_stage': 0,
        },
        {
            'task': 'EVENLY SPACED',
            'desc': ('Use np.linspace to make 5 evenly-spaced numbers from 0 to 1.\n'
                     'Print the array.\n'
                     'Expected to see:   0.   0.25  0.5  0.75  1.'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['0.25', '0.5', '0.75'],
            'hint': 'np.linspace(start, stop, count)',
            'requires_stage': 0,
        },
        {
            'task': 'COUNT BY TWOS',
            'desc': ('Use np.arange to make an array of even numbers from 0 up to (but not including) 10.\n'
                     'Print it.   Expected:   [0 2 4 6 8]'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['0', '2', '4', '6', '8'],
            'hint': 'np.arange(start, stop, step)  -- step = 2',
            'requires_stage': 0,
        },
    ],

    # ---------- LEVEL 4 :: 2D Arrays & Functions ----------
    # Stage map:  0=Functions (def/return/default params)
    #             1=is_even mini-quest    2=2D arrays (np.zeros((r,c)))
    4: [
        {
            'task': 'DOUBLE FUNCTION',
            'desc': ('Write a function `double(n)` that returns n * 2.\n'
                     'Then print double(7).\n'
                     'Expected output:   14'),
            'starter': '# Type your code here\n',
            'expected_contains': ['14'],
            'hint': 'def double(n):\n    return n * 2\nprint(double(7))',
            'requires_stage': 0,   # needs: def + return
        },
        {
            'task': 'IS POSITIVE',
            'desc': ('Write `is_positive(n)` that returns True if n > 0, else False.\n'
                     'Print is_positive(5) and is_positive(-3).\n'
                     'Expected:  True  then  False'),
            'starter': '# Type your code here\n',
            'expected_contains': ['True', 'False'],
            'hint': 'def is_positive(n):\n    return n > 0',
            'requires_stage': 0,
        },
        {
            'task': 'GREET BY NAME',
            'desc': ('Write `greet(name)` that prints   Hello, NAME!\n'
                     'Call greet("Alex"). Expected output:   Hello, Alex!'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Hello, Alex!'],
            'hint': 'def greet(name):\n    print(f"Hello, {name}!")',
            'requires_stage': 0,
        },
        {
            'task': '3x3 GRID OF ZEROS',
            'desc': ('Use numpy to make a 3x3 grid of zeros.\n'
                     'Set the centre cell (row 1, col 1) to 9.\n'
                     'Print the grid.'),
            'starter': 'import numpy as np\n# Type your code here\n',
            'expected_contains': ['9'],
            'hint': 'g = np.zeros((3, 3))\ng[1, 1] = 9\nprint(g)',
            'requires_stage': 2,   # needs: 2D arrays
        },
        {
            'task': 'SQUARE FUNCTION',
            'desc': ('Write `square(n)` that returns n * n.\n'
                     'Use a for-loop to print square(1) through square(5),\n'
                     'each on its own line.   Expected: 1 4 9 16 25'),
            'starter': '# Type your code here\n',
            'expected_contains': ['1', '4', '9', '16', '25'],
            'hint': 'def square(n):\n    return n * n\nfor i in range(1, 6):\n    print(square(i))',
            'requires_stage': 0,   # needs: def/return (for loops from L1)
        },
    ],

    # ---------- LEVEL 5 :: Files & Grids ----------
    # Stage map:  0=Writing a File  1=Reading a File  2=List Comprehensions
    5: [
        {
            'task': 'WRITE A FILE',
            'desc': ('Open a file named "out.txt" in write mode.\n'
                     'Write the line:  Hello from file!\n'
                     'Then print:  File written'),
            'starter': '# Type your code here\n',
            'expected_contains': ['File written'],
            'hint': 'with open("out.txt", "w") as f:\n    f.write("Hello from file!\\n")\nprint("File written")',
            'requires_stage': 0,
        },
        {
            'task': 'LIST COMP -- DOUBLES',
            'desc': ('Use a list comprehension to build a list of\n'
                     'each number from 1 to 5 doubled.\n'
                     'Print the list.   Expected:  [2, 4, 6, 8, 10]'),
            'starter': '# Type your code here\n',
            'expected_contains': ['2', '4', '6', '8', '10'],
            'hint': '[i * 2 for i in range(1, 6)]',
            'requires_stage': 2,
        },
        {
            'task': 'LIST COMP -- EVENS',
            'desc': ('Use a list comprehension to build a list of even numbers\n'
                     'from 0 to 19 (inclusive).\n'
                     'Print the list. Expected: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]'),
            'starter': '# Type your code here\n',
            'expected_contains': ['0', '2', '18'],
            'hint': '[i for i in range(20) if i % 2 == 0]',
            'requires_stage': 2,
        },
        {
            'task': 'WRITE THEN READ',
            'desc': ('Write the text "Saved!" into a file "note.txt".\n'
                     'Then open it in read mode, read the contents,\n'
                     'and print what you read.   Expected:  Saved!'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Saved!'],
            'hint': 'with open("note.txt","w") as f: f.write("Saved!")\nwith open("note.txt") as f: print(f.read())',
            'requires_stage': 1,   # needs: both write AND read
        },
        {
            'task': 'LIST COMP -- SQUARES',
            'desc': ('Use a list comprehension to build a list of the squares\n'
                     'of numbers 1 through 5.\n'
                     'Print the list. Expected: [1, 4, 9, 16, 25]'),
            'starter': '# Type your code here\n',
            'expected_contains': ['1', '4', '9', '16', '25'],
            'hint': '[i*i for i in range(1, 6)]',
            'requires_stage': 2,
        },
    ],

    # ---------- LEVEL 6 :: Classes & Objects ----------
    # Stage map:  0=Why Classes (reading)
    #             1=Your First Class (class/__init__/self/method that prints)
    #             2=Class vs Instance Variables
    #             3=Methods That Modify State (deposit/withdraw pattern)
    6: [
        {
            'task': 'BUILD A DOG',
            'desc': ('Write a class Dog with __init__(self, name).\n'
                     'Add a method bark(self) that prints:  NAME says Woof!\n'
                     'Create Dog("Rex") and call .bark()\n'
                     'Expected output:  Rex says Woof!'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Rex says Woof!'],
            'hint': 'class Dog:\n    def __init__(self, name): self.name = name\n    def bark(self): print(f"{self.name} says Woof!")',
            'requires_stage': 1,   # needs: class/__init__/method that prints
        },
        {
            'task': 'COUNTER CLASS',
            'desc': ('Make a class Counter with __init__ that sets self.n = 0.\n'
                     'Add a method inc(self) that increases self.n by 1.\n'
                     'Create one Counter, call inc() three times, then print c.n.\n'
                     'Expected output:  3'),
            'starter': '# Type your code here\n',
            'expected_contains': ['3'],
            'hint': 'class Counter:\n    def __init__(self): self.n = 0\n    def inc(self): self.n += 1',
            'requires_stage': 3,   # needs: method that MODIFIES self.x (deposit pattern)
        },
        {
            'task': 'BANK BALANCE',
            'desc': ('Class Account with __init__(self, balance).\n'
                     'Method deposit(self, amount) -> self.balance += amount.\n'
                     'Make Account(100), deposit 50, print acc.balance.\n'
                     'Expected output:  150'),
            'starter': '# Type your code here\n',
            'expected_contains': ['150'],
            'hint': 'class Account:\n    def __init__(self, balance): self.balance = balance\n    def deposit(self, amount): self.balance += amount',
            'requires_stage': 3,   # literally the deposit pattern from stage 3
        },
        {
            'task': 'RECTANGLE AREA',
            'desc': ('Class Rectangle with __init__(self, w, h).\n'
                     'Method area(self) returns w * h.\n'
                     'Make Rectangle(4, 5) and print r.area().\n'
                     'Expected output:  20'),
            'starter': '# Type your code here\n',
            'expected_contains': ['20'],
            'hint': 'class Rectangle:\n    def __init__(self, w, h): self.w, self.h = w, h\n    def area(self): return self.w * self.h',
            'requires_stage': 1,   # method that returns -- return is from L4
        },
        {
            'task': 'INTRODUCE YOURSELF',
            'desc': ('Class Person with __init__(self, name, age).\n'
                     'Method intro(self) prints: I am NAME, age AGE\n'
                     'Make Person("Sam", 21).intro()\n'
                     'Expected:  I am Sam, age 21'),
            'starter': '# Type your code here\n',
            'expected_contains': ['I am Sam, age 21'],
            'hint': 'class Person:\n    def __init__(self, name, age): self.name, self.age = name, age\n    def intro(self): print(f"I am {self.name}, age {self.age}")',
            'requires_stage': 1,
        },
    ],

    # ---------- LEVEL 7 :: Inheritance & Exceptions ----------
    # Stage map:  0=Three Class Relationships (reading)
    #             1=Inheritance (Person -> Staff, super(), override)
    #             2=Full People Hierarchy
    #             3=try/except
    #             4=try/except/else/finally
    7: [
        {
            'task': 'STUDENT EXTENDS PERSON',
            'desc': ('Class Person with __init__(self, name).\n'
                     'Class Student(Person) with __init__(self, name, sid)\n'
                     '   that calls super().__init__(name) and stores self.sid = sid.\n'
                     'Make Student("Alex", "S123") and print s.name and s.sid.\n'
                     'Expected lines: Alex   then   S123'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Alex', 'S123'],
            'hint': 'super().__init__(name) runs the parent init for you.',
            'requires_stage': 1,   # needs: inheritance + super()
        },
        {
            'task': 'CATCH VALUEERROR',
            'desc': ('Wrap  int("hello")  in try/except.\n'
                     'In the except block print:  Bad number\n'
                     'Expected output:  Bad number'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Bad number'],
            'hint': 'try:\n    int("hello")\nexcept ValueError:\n    print("Bad number")',
            'requires_stage': 3,   # needs: try/except
        },
        {
            'task': 'CATCH ZERODIVISION',
            'desc': ('Try to compute 10 / 0 inside try/except.\n'
                     'In the except block print:  Cannot divide\n'
                     'Expected output:  Cannot divide'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Cannot divide'],
            'hint': 'except ZeroDivisionError:',
            'requires_stage': 3,
        },
        {
            'task': 'ANIMAL -> CAT',
            'desc': ('Class Animal with method speak(self) that prints "Some sound".\n'
                     'Class Cat(Animal) with speak(self) that prints "Meow".\n'
                     'Create Cat() and call .speak().\n'
                     'Expected output:  Meow'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Meow'],
            'hint': 'Override speak() in the Cat subclass.',
            'requires_stage': 1,   # needs: inheritance + method override
        },
        {
            'task': 'TRY / EXCEPT / FINALLY',
            'desc': ('Inside a try block, do  x = int("nope")  (will fail).\n'
                     'In except print:  Caught\n'
                     'In finally print:  Done\n'
                     'Expected output:  Caught   then   Done'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Caught', 'Done'],
            'hint': 'try: ... except ValueError: print("Caught") finally: print("Done")',
            'requires_stage': 4,   # needs: finally clause
        },
    ],

    # ---------- LEVEL 8 :: Scripts & Automation ----------
    # Stage map:  0=Command-Line Arguments (sys.argv)   1=Parameter Sweep
    8: [
        {
            'task': 'FAKE THE ARGS',
            'desc': ('Set sys.argv = ["prog.py", "hello"].\n'
                     'Print sys.argv[1].\n'
                     'Expected output:  hello'),
            'starter': 'import sys\n# Type your code here\n',
            'expected_contains': ['hello'],
            'hint': 'sys.argv[1] is the first user argument.',
            'requires_stage': 0,
        },
        {
            'task': 'COUNT THE ARGS',
            'desc': ('Set sys.argv = ["prog.py", "a", "b", "c"].\n'
                     'Print:  Got 3 args\n'
                     '(Hint: that is len(sys.argv) - 1)'),
            'starter': 'import sys\n# Type your code here\n',
            'expected_contains': ['Got 3 args'],
            'hint': 'print(f"Got {len(sys.argv)-1} args")',
            'requires_stage': 0,
        },
        {
            'task': 'ARG TO INT',
            'desc': ('Set sys.argv = ["prog.py", "5"].\n'
                     'Convert sys.argv[1] to int and print its square.\n'
                     'Expected output:  25'),
            'starter': 'import sys\n# Type your code here\n',
            'expected_contains': ['25'],
            'hint': 'n = int(sys.argv[1]); print(n*n)',
            'requires_stage': 0,
        },
        {
            'task': 'PARAMETER SWEEP',
            'desc': ('For each rate in [0.1, 0.2, 0.3], print:  rate=R\n'
                     'Expected to see:  rate=0.1   rate=0.2   rate=0.3'),
            'starter': '# Type your code here\n',
            'expected_contains': ['0.1', '0.2', '0.3'],
            'hint': 'for r in [0.1, 0.2, 0.3]:\n    print(f"rate={r}")',
            'requires_stage': 1,   # parameter-sweep pattern from stage 1
        },
        {
            'task': 'SCRIPT NAME',
            'desc': ('Set sys.argv = ["myscript.py"].\n'
                     'Print:  Script: myscript.py'),
            'starter': 'import sys\n# Type your code here\n',
            'expected_contains': ['Script: myscript.py'],
            'hint': 'print(f"Script: {sys.argv[0]}")',
            'requires_stage': 0,
        },
    ],

    # ---------- LEVEL 9 :: Quality & Testing ----------
    # Stage map:  0=assert  1=Fix The Broken Code  2=PyPI (reading)
    9: [
        {
            'task': 'ASSERT IT',
            'desc': ('Write a function add(a, b) that returns a + b.\n'
                     'Then assert add(2, 3) == 5.\n'
                     'After the assert, print:  All good'),
            'starter': '# Type your code here\n',
            'expected_contains': ['All good'],
            'hint': 'assert raises AssertionError if False; passes silently if True.',
            'requires_stage': 0,
        },
        {
            'task': 'CATCH BAD ASSERT',
            'desc': ('Inside a try block:  assert 1 == 2, "math is broken"\n'
                     'Catch the AssertionError and print the message it carried.\n'
                     'Expected output:  math is broken'),
            'starter': '# Type your code here\n',
            'expected_contains': ['math is broken'],
            'hint': 'except AssertionError as e: print(e)',
            'requires_stage': 0,   # L7 taught try/except; L9-0 shows assert+except AssertionError
        },
        {
            'task': 'FIX THE BUG',
            'desc': ('The starter has a buggy / instead of //.\n'
                     'Fix it so range works without crashing.\n'
                     "After fixing, print:  Fixed"),
            'starter': '# Fix the bug below, then keep the print at the end\nfor i in range(10 / 2):\n    pass\nprint("Fixed")\n',
            'expected_contains': ['Fixed'],
            'hint': 'range() needs an int. Use //  (integer division).',
            'requires_stage': 1,
        },
        {
            'task': 'GUARD WITH ASSERT',
            'desc': ('Write divide(a, b) that asserts b != 0 (custom message: "no zero")\n'
                     'and returns a / b.  Call divide(10, 2) and print the result.\n'
                     'Expected output:  5.0'),
            'starter': '# Type your code here\n',
            'expected_contains': ['5.0'],
            'hint': 'assert b != 0, "no zero"',
            'requires_stage': 0,
        },
        {
            'task': 'TEST WITH ASSERT',
            'desc': ('Write a function is_even(n) that returns True if n % 2 == 0.\n'
                     'Add three asserts:  is_even(0), not is_even(3), is_even(8).\n'
                     'After all pass, print:  Tests passed'),
            'starter': '# Type your code here\n',
            'expected_contains': ['Tests passed'],
            'hint': 'assert is_even(0)   assert not is_even(3)   assert is_even(8)',
            'requires_stage': 0,
        },
    ],

    # ---------- LEVEL 10 :: Data Processing ----------
    # Stage map:  0=The Data Pipeline (read, parse, dict counts, max+lambda)
    10: [
        {
            'task': 'SUM A LIST',
            'desc': ('Given scores = [85, 72, 90, 68].\n'
                     'Print:  Total: 315'),
            'starter': '# Type your code here\nscores = [85, 72, 90, 68]\n',
            'expected_contains': ['Total: 315'],
            'hint': 'print(f"Total: {sum(scores)}")',
            'requires_stage': 0,
        },
        {
            'task': 'AVERAGE A LIST',
            'desc': ('Given scores = [80, 70, 60].\n'
                     'Print the average to 1 decimal place:   Average: 70.0'),
            'starter': '# Type your code here\nscores = [80, 70, 60]\n',
            'expected_contains': ['Average: 70.0'],
            'hint': 'avg = sum(scores) / len(scores)',
            'requires_stage': 0,
        },
        {
            'task': 'COUNT BY KEY',
            'desc': ('Given fruits = ["apple", "pear", "apple", "lime", "apple", "pear"].\n'
                     'Build a dict counting each fruit, then print it.\n'
                     'Expected counts to include: apple 3, pear 2, lime 1'),
            'starter': '# Type your code here\nfruits = ["apple", "pear", "apple", "lime", "apple", "pear"]\n',
            'expected_contains': ['3', '2', '1'],
            'hint': 'counts = {}\nfor f in fruits:\n    counts[f] = counts.get(f, 0) + 1',
            'requires_stage': 0,
        },
        {
            'task': 'PARSE A CSV LINE',
            'desc': ('Set  line = "Alex,Python,85".\n'
                     'Split on commas, then print:\n'
                     '  Name: Alex\n  Subject: Python\n  Score: 85'),
            'starter': '# Type your code here\nline = "Alex,Python,85"\n',
            'expected_contains': ['Alex', 'Python', '85'],
            'hint': 'parts = line.split(",")  -> use parts[0], parts[1], parts[2]',
            'requires_stage': 0,
        },
        {
            'task': 'TOP SCORE',
            'desc': ('Given records = [{"name":"Alex","score":80}, {"name":"Sam","score":95}, {"name":"Jo","score":72}].\n'
                     'Find the record with the highest score.\n'
                     'Print:  Top: Sam (95)'),
            'starter': '# Type your code here\nrecords = [{"name":"Alex","score":80},{"name":"Sam","score":95},{"name":"Jo","score":72}]\n',
            'expected_contains': ['Top: Sam (95)'],
            'hint': 'top = max(records, key=lambda r: r["score"])',
            'requires_stage': 0,
        },
    ],

    # ---------- LEVEL 11 :: Applications ----------
    # Stage map:  0=Projectile Motion (math.sin/cos/radians/pi)  1=What's Next
    11: [
        {
            'task': 'CIRCLE AREA',
            'desc': ('Use math.pi to compute the area of a circle with radius 5.\n'
                     'Print to 2 decimals:   Area: 78.54'),
            'starter': 'import math\n# Type your code here\n',
            'expected_contains': ['Area: 78.54'],
            'hint': 'area = math.pi * 5 ** 2',
            'requires_stage': 0,
        },
        {
            'task': 'CONVERT TO RADIANS',
            'desc': ('Convert 90 degrees to radians using math.radians().\n'
                     'Print to 4 decimals:   1.5708'),
            'starter': 'import math\n# Type your code here\n',
            'expected_contains': ['1.5708'],
            'hint': 'print(f"{math.radians(90):.4f}")',
            'requires_stage': 0,
        },
        {
            'task': 'PROJECTILE FLIGHT TIME',
            'desc': ('Given v0 = 20 m/s upward and g = 9.81.\n'
                     'Print flight time as t = 2*v0/g, formatted to 2 decimals.\n'
                     'Expected:  Flight: 4.08 s'),
            'starter': 'g = 9.81\nv0 = 20\n# Type your code here\n',
            'expected_contains': ['Flight: 4.08 s'],
            'hint': 'print(f"Flight: {2*v0/g:.2f} s")',
            'requires_stage': 0,
        },
        {
            'task': 'SQUARE ROOT TABLE',
            'desc': ('Use math.sqrt() in a loop to print the square roots\n'
                     'of 1, 4, 9, 16. Each on its own line.\n'
                     'Expected: 1.0  2.0  3.0  4.0'),
            'starter': 'import math\n# Type your code here\n',
            'expected_contains': ['1.0', '2.0', '3.0', '4.0'],
            'hint': 'for n in [1, 4, 9, 16]:\n    print(math.sqrt(n))',
            'requires_stage': 0,
        },
        {
            'task': 'SIMPLE SIMULATION',
            'desc': ('Start with infected = 1.\n'
                     'Loop 5 times: each time, set infected = infected * 2.\n'
                     'After the loop, print:  Final: 32'),
            'starter': '# Type your code here\ninfected = 1\n',
            'expected_contains': ['Final: 32'],
            'hint': 'for _ in range(5):\n    infected = infected * 2\nprint(f"Final: {infected}")',
            'requires_stage': 0,
        },
    ],
}


# =============================================================================
#  QUIZ VARIATIONS  (NEW FEATURE)
# -----------------------------------------------------------------------------
#  Each level has 7 quiz variations. When the level is opened, ONE is randomly
#  selected and shown as the Boss Quiz. Same shape as the original 'quiz' key.
# =============================================================================
QUIZ_VARIATIONS = {
    # ---------- LEVEL 1 ----------
    1: [
        {'q': "What will this print?\n\nfor i in range(3):\n    print(i * 2)",
         'options': ["0 2 4", "2 4 6", "0 1 2", "1 2 3"], 'correct': 0,
         'explain': "range(3) gives 0,1,2. Each x 2 = 0,2,4."},
        {'q': "What does input() always return?",
         'options': ["A number", "A string", "A boolean", "Whatever type the user typed"],
         'correct': 1,
         'explain': "input() ALWAYS returns a string. Cast with int() or float() if you need a number."},
        {'q': "Which operator means 'not equal' in Python?",
         'options': ["<>", "!=", "=/=", "not="], 'correct': 1,
         'explain': "!= is 'not equal'. == is 'equal'. = is assignment."},
        {'q': "What does this print?\n\nx = 5\nif x > 10:\n    print('A')\nelif x > 3:\n    print('B')\nelse:\n    print('C')",
         'options': ["A", "B", "C", "Nothing"], 'correct': 1,
         'explain': "x > 10 is False, but x > 3 is True, so the elif branch runs and prints B."},
        {'q': "Which Linux command shows your current directory?",
         'options': ["cd", "ls", "pwd", "dir"], 'correct': 2,
         'explain': "pwd = 'print working directory'. ls lists files; cd changes directory."},
        {'q': "What's the difference between = and == in Python?",
         'options': ["No difference", "= assigns a value, == compares two values",
                     "= compares, == assigns", "Both compare values"], 'correct': 1,
         'explain': "= stores a value into a variable. == checks if two values are equal."},
        {'q': "How many times will this loop run?\n\nwhile False:\n    print('hi')",
         'options': ["0", "1", "Infinite", "Error"], 'correct': 0,
         'explain': "The condition is False at the start, so the loop body never runs."},
    ],

    # ---------- LEVEL 2 ----------
    2: [
        {'q': 'Given s = "programming", what does s[3:7] give?',
         'options': ['"gram"', '"gramm"', '"prog"', '"ramm"'], 'correct': 0,
         'explain': "Index 3 to 6 inclusive (7 is excluded) = 'g','r','a','m' = 'gram'."},
        {'q': 'What does "hello".upper() return?',
         'options': ['"HELLO"', '"Hello"', '"hello"', 'Nothing - it modifies the string'],
         'correct': 0,
         'explain': "Upper returns a NEW string in uppercase. Strings in Python are immutable."},
        {'q': 'What is the index of "P" in "PYTHON"?',
         'options': ['1', '0', '-1', '6'], 'correct': 1,
         'explain': "Indexes start at 0. P is the first letter, so its index is 0."},
        {'q': "What does 'a,b,c'.split(',') return?",
         'options': ["'abc'", "['a','b','c']", "('a','b','c')", "Error"], 'correct': 1,
         'explain': "split(',') divides the string at each comma and returns a list."},
        {'q': "fruits = ['apple', 'pear']\nfruits.append('lime')\nprint(len(fruits))\n\nWhat is printed?",
         'options': ["1", "2", "3", "Error"], 'correct': 2,
         'explain': "append adds 'lime' to the list. Now there are 3 items, so len is 3."},
        {'q': 'word = "PYTHON"\nprint(word[-1])\n\nWhat is printed?',
         'options': ['P', 'N', 'O', 'Error'], 'correct': 1,
         'explain': "Negative indexes count from the end. -1 = last character = 'N'."},
        {'q': "Which of these MODIFIES the original list?",
         'options': ["a.upper()", "fruits.append('x')", "word[0:3]", "len(items)"],
         'correct': 1,
         'explain': "Lists are mutable -- append modifies the list in place. String methods like upper() return NEW strings."},
    ],

    # ---------- LEVEL 3 ----------
    3: [
        {'q': "What's the main advantage of numpy arrays over lists for numerical work?",
         'options': ["They hold mixed types.", "Vectorised math -- you can do `arr * 2` instead of looping.",
                     "They auto-sort.", "They're always 2D."], 'correct': 1,
         'explain': "Arrays support element-wise math on the whole array at once. Faster + cleaner."},
        {'q': "What does np.zeros(4) produce?",
         'options': ["[]", "[0, 0, 0, 0]", "[0., 0., 0., 0.]", "Error"], 'correct': 2,
         'explain': "np.zeros(4) makes a length-4 array of zeros (floats by default)."},
        {'q': "If arr = np.array([1, 2, 3]), what does arr * 3 give?",
         'options': ["[3, 6, 9]", "[1, 2, 3, 1, 2, 3, 1, 2, 3]", "9", "Error"],
         'correct': 0,
         'explain': "Numpy multiplies element-wise. With lists, * 3 would REPEAT the list. Big difference!"},
        {'q': "What does np.arange(0, 10, 2) produce?",
         'options': ["[0, 2, 4, 6, 8]", "[0, 2, 4, 6, 8, 10]", "[2, 4, 6, 8, 10]",
                     "[0, 1, 2, ..., 10]"], 'correct': 0,
         'explain': "arange(start, stop, step). Stop is EXCLUDED. So 0, 2, 4, 6, 8 (no 10)."},
        {'q': "Which gives 5 evenly-spaced values from 0 to 1 (inclusive of both)?",
         'options': ["np.arange(0, 1, 5)", "np.linspace(0, 1, 5)",
                     "np.zeros(5)", "np.array(0, 1, 5)"], 'correct': 1,
         'explain': "linspace(start, stop, count) -- both endpoints included. arange uses a step instead."},
        {'q': "Why use matplotlib.use('Agg') in this app's plotting examples?",
         'options': ["To make plots faster", "To use a non-interactive backend that won't freeze the window",
                     "To enable colours", "To save memory"], 'correct': 1,
         'explain': "Agg = non-GUI backend. Safer when embedded inside another app."},
        {'q': "arr = np.array([10, 20, 30])\nprint(arr.mean())\n\nWhat does this print?",
         'options': ["10", "20.0", "30", "60"], 'correct': 1,
         'explain': "(10 + 20 + 30) / 3 = 20.0. Mean returns a float."},
    ],

    # ---------- LEVEL 4 ----------
    4: [
        {'q': "What's the difference between print() and return in a function?",
         'options': ["They're the same.",
                     "print shows to the user; return hands a value back to the caller.",
                     "return is only for numbers.", "print is faster."], 'correct': 1,
         'explain': "print = output to screen. return = give value back. x = square(5) needs return."},
        {'q': "def f(): print('hi')\nx = f()\nprint(x)\n\nWhat is printed?",
         'options': ["hi", "hi\\nNone", "None", "Error"], 'correct': 1,
         'explain': "f() prints 'hi' but returns None. So x = None, then print(x) shows None."},
        {'q': "In def greet(name='friend'): ..., what is 'friend'?",
         'options': ["The variable name", "A default value -- used if no arg is passed",
                     "A docstring", "An error"], 'correct': 1,
         'explain': "Default argument value. greet() with no args uses 'friend'."},
        {'q': "How do you make a 2D array of zeros with 3 rows and 4 columns?",
         'options': ["np.zeros(3, 4)", "np.zeros((3, 4))", "np.zeros[3][4]",
                     "np.zeros(3*4)"], 'correct': 1,
         'explain': "Pass a TUPLE for the shape: (3, 4). Single number gives a 1D array."},
        {'q': "grid = np.zeros((3, 3))\ngrid[1, 2] = 5\n\nWhich cell gets set to 5?",
         'options': ["First row, first col", "Second row, third col",
                     "Third row, second col", "Centre cell"], 'correct': 1,
         'explain': "Indexes are 0-based. [1, 2] = row index 1 (second row), col index 2 (third col)."},
        {'q': "To loop through every cell in a 2D grid, you typically use:",
         'options': ["A single for loop", "Two nested for loops (rows then cols)",
                     "while True", "A list comp only"], 'correct': 1,
         'explain': "Outer loop = rows, inner loop = cols. Standard pattern for grids."},
        {'q': "def square(n): return n * n\nprint(square(4))\n\nWhat is printed?",
         'options': ["8", "16", "44", "None"], 'correct': 1,
         'explain': "4 * 4 = 16. The function returns 16 and print displays it."},
    ],

    # ---------- LEVEL 5 ----------
    5: [
        {'q': 'You open a file with open("log.txt", "w"). The file already existed with content. What happens?',
         'options': ["Content is appended to the end.", "Python raises an error.",
                     "Old content is wiped and replaced.", "File is duplicated."], 'correct': 2,
         'explain': "Mode 'w' = write from scratch. Old content is DELETED. Use 'a' to append."},
        {'q': "What does the 'with' statement do for files?",
         'options': ["Locks the file forever",
                     "Auto-closes the file when the block ends, even on errors",
                     "Makes file access faster", "Encrypts the file"], 'correct': 1,
         'explain': "with open(...) as f: -- file auto-closes when you exit the block. Safer than open/close manually."},
        {'q': "Which mode is for APPENDING to an existing file?",
         'options': ['"w"', '"r"', '"a"', '"+"'], 'correct': 2,
         'explain': "'a' = append. Adds to the end. 'w' wipes; 'r' is read-only."},
        {'q': "What does [i*i for i in range(4)] produce?",
         'options': ["[0, 1, 2, 3]", "[0, 1, 4, 9]", "[1, 4, 9, 16]", "[1, 2, 3, 4]"],
         'correct': 1,
         'explain': "range(4) = 0,1,2,3. Squared: 0,1,4,9."},
        {'q': "Why use .strip() on lines from a file?",
         'options': ["To remove the file extension",
                     "To remove leading/trailing whitespace including newline characters",
                     "To delete the line", "To lowercase it"], 'correct': 1,
         'explain': "Lines from a file end with '\\n'. strip() removes that and any other surrounding whitespace."},
        {'q': "[x for x in range(10) if x % 2 == 1]   produces what?",
         'options': ["Even numbers 0..8", "Odd numbers 1..9", "All numbers 0..9", "Empty list"],
         'correct': 1,
         'explain': "x % 2 == 1 is True for odd numbers. So you get [1, 3, 5, 7, 9]."},
        {'q': "Which read method gives you ONE BIG string of the whole file?",
         'options': [".readline()", ".readlines()", ".read()", ".readall()"], 'correct': 2,
         'explain': "f.read() returns the whole file as one string. readlines() returns a list. readline() returns one line."},
    ],

    # ---------- LEVEL 6 ----------
    6: [
        {'q': "Inside a class, what does `self` refer to?",
         'options': ["The class itself (e.g. Animal).", "The specific object instance the method was called on.",
                     "A built-in variable you can't rename.", "The main program."], 'correct': 1,
         'explain': "self is the SPECIFIC object. rex.printit() -> self = rex."},
        {'q': "When does __init__ run?",
         'options': ["Once when Python starts", "Every time you call the class to make a new object",
                     "Only if you call it explicitly", "Never -- it's a placeholder"], 'correct': 1,
         'explain': "__init__ is the constructor. It runs every time you do MyClass(...) to build a new object."},
        {'q': "What's the difference between class and instance variables?",
         'options': ["No difference", "Class vars are SHARED by all instances; instance vars are unique per object",
                     "Instance vars are faster", "Class vars are private"], 'correct': 1,
         'explain': "Class var = one copy, shared. Instance var (self.x) = one copy per object."},
        {'q': "What's wrong with:\n\nclass Dog:\n    def bark():\n        print('Woof!')\n\nrex = Dog()\nrex.bark()",
         'options': ["Nothing -- works fine", "Missing self parameter -- bark(self)",
                     "Class needs __init__", "print is wrong"], 'correct': 1,
         'explain': "First parameter of every method must be self. Forgetting it is the #1 beginner bug."},
        {'q': "What does a CLASS represent vs an OBJECT?",
         'options': ["Same thing", "Class = blueprint, Object = one specific thing built from the blueprint",
                     "Class = newer, Object = older", "Class = small, Object = big"], 'correct': 1,
         'explain': "Class = blueprint (e.g. 'Dog'). Object = one actual thing made from it (e.g. Rex the labrador)."},
        {'q': "How do you call a method 'speak' on object 'rex'?",
         'options': ["speak(rex)", "rex.speak()", "Dog.speak()", "rex->speak"], 'correct': 1,
         'explain': "Use dot notation: object.method(). Python passes 'rex' in as 'self' automatically."},
        {'q': "class Cat:\n    species = 'feline'\n\na = Cat()\nb = Cat()\nCat.species = 'kitty'\nprint(a.species)\n\nWhat is printed?",
         'options': ["feline", "kitty", "Cat", "Error"], 'correct': 1,
         'explain': "species is a class variable -- shared. Changing Cat.species changes what every instance sees."},
    ],

    # ---------- LEVEL 7 ----------
    7: [
        {'q': "Inside a subclass, what does super().__init__(name, dob) do?",
         'options': ["Creates a new parent object with those values.",
                     "Runs the parent's __init__ method on THIS object, so parent's fields get set up.",
                     "Renames the class.", "Deletes the parent class."], 'correct': 1,
         'explain': "super() gives you the parent class. super().__init__(...) runs the parent's init on self."},
        {'q': "What's the relationship called when 'A Dog IS AN Animal'?",
         'options': ["Composition", "Aggregation", "Inheritance", "Encapsulation"], 'correct': 2,
         'explain': "IS-A = inheritance. HAS-A (strong) = composition. HAS-A (weak) = aggregation."},
        {'q': "Which exception is raised by  int('hello')?",
         'options': ["TypeError", "ValueError", "NameError", "SyntaxError"], 'correct': 1,
         'explain': "ValueError -- the type is right (str), but the value can't be converted to int."},
        {'q': "Which exception is raised by  10 / 0?",
         'options': ["MathError", "ValueError", "ZeroDivisionError", "ArithmeticError"], 'correct': 2,
         'explain': "ZeroDivisionError. (Yes, also a subclass of ArithmeticError, but Python names the specific one.)"},
        {'q': "What does the `finally` clause do in try/except/finally?",
         'options': ["Runs only if no exception", "Runs only if an exception occurred",
                     "Runs ALWAYS, even if there was an exception", "Runs after the program ends"],
         'correct': 2,
         'explain': "finally always runs -- perfect for cleanup like closing files or releasing locks."},
        {'q': "class Postgrad(Student): pass\n\nWhat does Postgrad inherit from Student?",
         'options': ["Nothing -- pass means empty", "All Student's methods and attributes",
                     "Only the constructor", "Only methods, not attributes"], 'correct': 1,
         'explain': "pass = empty body. The CLASS still inherits everything from Student."},
        {'q': "If you forget to call super().__init__() in a subclass, what's likely?",
         'options': ["No problem", "AttributeError when accessing parent's fields",
                     "SyntaxError", "The subclass becomes the parent"], 'correct': 1,
         'explain': "Parent's __init__ never runs, so its fields never get set. Accessing them = AttributeError."},
    ],

    # ---------- LEVEL 8 ----------
    8: [
        {'q': "Running `python3 myprog.py hello 42`, what does sys.argv[0] contain?",
         'options': ["'hello'", "'42'", "'myprog.py' (the script name)", "An empty string"],
         'correct': 2,
         'explain': "sys.argv[0] is always the script name. User args start at index 1."},
        {'q': "What type are the items in sys.argv?",
         'options': ["int", "str", "Whatever the user typed", "bytes"], 'correct': 1,
         'explain': "All sys.argv items are strings -- even '42'. Cast with int() if you need a number."},
        {'q': "Which package is best for command-line argument parsing in real scripts?",
         'options': ["sys", "os", "argparse", "shutil"], 'correct': 2,
         'explain': "sys.argv is the basic mechanism. argparse builds on it -- adds flags, help, type checking."},
        {'q': "What's a 'parameter sweep'?",
         'options': ["Cleaning unused parameters",
                     "Running a simulation many times with different parameter values",
                     "Renaming function parameters", "A type of for loop"], 'correct': 1,
         'explain': "Standard scientific computing pattern: for each parameter value, run the experiment, log the result."},
        {'q': "If sys.argv = ['x.py'], what does len(sys.argv) - 1 tell you?",
         'options': ["The script name length", "The number of USER arguments (here, 0)",
                     "1", "An error"], 'correct': 1,
         'explain': "len includes the script name. -1 gives the count of actual user-supplied args."},
        {'q': "What does sys.exit() do?",
         'options': ["Exits the function", "Exits Python immediately",
                     "Exits the loop", "Saves and exits"], 'correct': 1,
         'explain': "Exits the whole program. Common usage: bad arguments -> print usage, sys.exit()."},
        {'q': "Where does the os module help (vs sys)?",
         'options': ["With math operations", "With operating system tasks: paths, dirs, env vars",
                     "With networking", "With strings"], 'correct': 1,
         'explain': "os = operating system interface. sys = the Python interpreter."},
    ],

    # ---------- LEVEL 9 ----------
    9: [
        {'q': "Which of these is the BEST signal a PyPI package is safe to depend on?",
         'options': ["It has a cool logo.", "Version 0.2.1, last updated 3 years ago.",
                     "Version 2.5, updated last week, 40+ contributors, active issue tracking.",
                     "It's mentioned in one tutorial."], 'correct': 2,
         'explain': "Stable version, recent activity, multiple contributors, responsive issues = trustworthy."},
        {'q': "What does  assert x > 0  do if x is -5?",
         'options': ["Sets x to 0", "Raises AssertionError",
                     "Returns False silently", "Prints a warning"], 'correct': 1,
         'explain': "assert raises AssertionError if the condition is False. Crashes loudly = good for catching bugs."},
        {'q': "Why is integer division (//) needed in  range(10/2)?",
         'options': ["For speed", "Because range needs an int, but / always gives a float",
                     "Because // is more accurate", "There is no difference"], 'correct': 1,
         'explain': "10 / 2 = 5.0 (float). range() needs an int. 10 // 2 = 5 (int). Use //."},
        {'q': "What's the SYNTAX bug in:   if x = 5:",
         'options': ["x is not defined", "= should be ==",
                     "Missing colon... wait, there is one. Hmm.", "Missing parentheses"], 'correct': 1,
         'explain': "= is assignment. == is comparison. if needs a comparison."},
        {'q': "What is unit testing?",
         'options': ["Testing the user interface",
                     "Writing small tests for individual pieces (units) of code",
                     "Testing only one feature at a time", "A type of debugging tool"], 'correct': 1,
         'explain': "Unit tests check individual functions/methods (units). assert is the simplest form."},
        {'q': "Which is a good 'sanity check' tool while developing?",
         'options': ["print()", "assert", "Both -- they complement each other", "Neither, use a debugger"],
         'correct': 2,
         'explain': "print shows you what's happening; assert catches when assumptions break. Both are valuable."},
        {'q': "Which version number suggests a STABLE library?",
         'options': ["0.0.1", "0.9.0", "1.0+", "2.5-beta"], 'correct': 2,
         'explain': "Convention: pre-1.0 = under active development, breaking changes possible. 1.0+ signals stability."},
    ],

    # ---------- LEVEL 10 ----------
    10: [
        {'q': "In the pipeline code, why do we use `int(parts[2])` when reading the score?",
         'options': ["To speed up the code.",
                     "Because split() always returns strings -- we need a number to do math.",
                     "Because CSV files are binary.", "To save memory."], 'correct': 1,
         'explain': "split returns strings. '85' and 85 are different -- can't do math on strings."},
        {'q': "What does dict.get('key', 0) do?",
         'options': ["Sets the key to 0", "Returns the value if the key exists, else 0",
                     "Removes the key", "Raises an error"], 'correct': 1,
         'explain': "get(key, default) -- safer than dict[key] which would raise KeyError if missing."},
        {'q': "Which is the typical data pipeline order?",
         'options': ["Output -> read -> clean -> compute",
                     "Read -> parse/clean -> compute -> output",
                     "Compute -> read -> output -> clean",
                     "Clean -> output -> compute -> read"], 'correct': 1,
         'explain': "Standard: get the data in, clean it, do the analysis, report the result."},
        {'q': "max(records, key=lambda r: r['score'])  -- what does this do?",
         'options': ["Returns the highest score number",
                     "Returns the record (dict) with the highest score",
                     "Errors -- can't max dicts", "Returns the first record"], 'correct': 1,
         'explain': "max with key=lambda picks the item where lambda returns the biggest value. You get the WHOLE record."},
        {'q': "Reading a CSV line 'Alex,Python,85', .split(',') gives:",
         'options': ["A string 'AlexPython85'", "A list ['Alex', 'Python', '85']",
                     "A tuple", "A dict"], 'correct': 1,
         'explain': "split returns a list of strings. Each item is one comma-separated piece."},
        {'q': "What does pandas give you that lists/dicts don't?",
         'options': ["Nothing new", "DataFrames -- table-like structures with columns, easy aggregation, filtering",
                     "Faster math", "Built-in plots only"], 'correct': 1,
         'explain': "pandas DataFrames = labelled rows + columns + powerful operations like groupby and merge."},
        {'q': "Why might you write .strip() when reading lines from a CSV?",
         'options': ["To remove the comma", "To remove the trailing newline ('\\n')",
                     "To shorten the line", "To convert to lowercase"], 'correct': 1,
         'explain': "Lines from files include '\\n'. strip() removes whitespace including newlines."},
    ],

    # ---------- LEVEL 11 ----------
    11: [
        {'q': "At what angle does an ideal projectile travel furthest (no air resistance)?",
         'options': ["30 deg", "45 deg", "60 deg", "90 deg"], 'correct': 1,
         'explain': "45 deg balances horizontal velocity vs airtime. Provable computationally."},
        {'q': "math.radians(180) returns approximately what?",
         'options': ["180", "pi (~3.14)", "0", "1"], 'correct': 1,
         'explain': "180 degrees = pi radians ≈ 3.14159."},
        {'q': "Why does scientific computing prefer numpy arrays over Python lists?",
         'options': ["Smaller files", "Vectorised operations -- much faster for big datasets",
                     "More colours", "Built-in plots"], 'correct': 1,
         'explain': "numpy uses C under the hood -- vector ops on arrays of millions of elements stay fast."},
        {'q': "Which library is for numerical arrays + math?",
         'options': ["matplotlib", "numpy", "pandas", "tkinter"], 'correct': 1,
         'explain': "numpy = numerical Python. matplotlib = plotting. pandas = data tables. tkinter = GUI."},
        {'q': "Which library is for plotting?",
         'options': ["numpy", "matplotlib", "pandas", "json"], 'correct': 1,
         'explain': "matplotlib.pyplot is the standard Python plotting library."},
        {'q': "math.sqrt(16) returns:",
         'options': ["4", "4.0", "8", "256"], 'correct': 1,
         'explain': "sqrt always returns a float. 4.0 (not 4)."},
        {'q': "Which field below DOES use Python heavily?",
         'options': ["Only web design", "Only games",
                     "Data science, engineering, GIS, bioinformatics, and many more", "Only embedded systems"],
         'correct': 2,
         'explain': "Python is everywhere data and automation matter. The fundamentals you learned go a long way."},
    ],
}


def pick_stage_challenge(level_id, current_stage_idx=None):
    """
    Return one randomly-selected challenge for the given level.

    If `current_stage_idx` is given, only challenges whose `requires_stage`
    is <= current_stage_idx are eligible. This guarantees a student never
    sees a challenge that needs content they haven't been taught yet.
    """
    bank = STAGE_CHALLENGES.get(level_id, [])
    if not bank:
        return None
    if current_stage_idx is not None:
        eligible = [
            c for c in bank
            if c.get('requires_stage', 0) <= current_stage_idx
        ]
        if eligible:
            bank = eligible
        # If NOTHING is eligible yet (e.g. pure-reading stage 0 with no
        # matching challenges), return None so no challenge is shown.
        else:
            return None
    return random.choice(bank)


def pick_quiz_variation(level_id, fallback):
    """Return one of the 7 quiz variations for the level. Fall back if missing."""
    bank = QUIZ_VARIATIONS.get(level_id, [])
    if not bank:
        return fallback
    return random.choice(bank)


def check_challenge_output(challenge, output):
    """
    Compare the user's output to the challenge's expectations.
    Returns (passed: bool, message: str).
    """
    if 'expected_exact' in challenge:
        if output.strip() == challenge['expected_exact'].strip():
            return True, "Perfect -- output matches exactly."
        return False, ("Output didn't match the expected exact text.\n"
                       f"Expected:\n{challenge['expected_exact']}")

    if 'expected_contains' in challenge:
        missing = [s for s in challenge['expected_contains'] if str(s) not in output]
        if not missing:
            return True, "All expected text found in your output."
        nice = ', '.join(repr(m) for m in missing)
        return False, f"Output is missing these pieces: {nice}"

    return True, "Code ran without errors."




# =============================================================================
#  UI HELPER WIDGETS
# =============================================================================
class ScrollableFrame(tk.Frame):
    """
    A frame you can put any content in -- it scrolls with the mouse wheel.

    Mouse wheel behaviour:
      * Works ANYWHERE in the app window (we use bind_all to catch wheel
        events globally, no matter which child widget is under the cursor).
      * If the cursor is inside a tk.Text widget (e.g. a code editor or the
        output panel), the wheel scrolls THAT widget instead of the page,
        so you can scroll long code blocks independently.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=C['bg'])
        self.canvas = tk.Canvas(
            self, bg=C['bg'], highlightthickness=0, bd=0, **kwargs
        )
        self.scrollbar = tk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=C['bg'])

        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)

        self.inner.bind('<Configure>', self._on_inner_config)
        self.canvas.bind('<Configure>', self._on_canvas_config)

        # Global wheel binding -- catches events anywhere in the app window.
        # We only do this once (it's a global binding on the toplevel).
        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel_global, add='+')
        self.canvas.bind_all('<Button-4>',   self._on_button4_global,    add='+')
        self.canvas.bind_all('<Button-5>',   self._on_button5_global,    add='+')

    def _on_inner_config(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_config(self, event):
        self.canvas.itemconfig(self._window_id, width=event.width)

    def _cursor_over_text_widget(self, event):
        """True if the wheel event happened inside a tk.Text widget."""
        w = event.widget
        return isinstance(w, tk.Text)

    def _on_mousewheel_global(self, event):
        # Inside a Text widget? Let it scroll itself.
        if self._cursor_over_text_widget(event):
            return
        # Windows: event.delta is +/-120 per notch
        # macOS:   event.delta is much smaller (per-pixel)
        if abs(event.delta) >= 120:
            steps = -int(event.delta / 120) * 3
        else:
            steps = -int(event.delta) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(steps, 'units')

    def _on_button4_global(self, event):
        # Linux: wheel up
        if self._cursor_over_text_widget(event):
            return
        self.canvas.yview_scroll(-3, 'units')

    def _on_button5_global(self, event):
        # Linux: wheel down
        if self._cursor_over_text_widget(event):
            return
        self.canvas.yview_scroll(3, 'units')

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)


def neon_button(parent, text, command=None, colour='neon_green', style='solid',
                font_key='arcade_sm', padx=14, pady=8, **kwargs):
    """A styled retro button."""
    if style == 'solid':
        bg = C[colour]
        fg = C['bg']
        active_bg = C['neon_cyan']
    else:  # outline
        bg = C['bg']
        fg = C[colour]
        active_bg = C[colour]
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg,
        activebackground=active_bg,
        activeforeground=C['bg'],
        font=FONTS[font_key],
        relief='flat', bd=0,
        padx=padx, pady=pady,
        cursor='hand2',
        **kwargs,
    )
    if style == 'outline':
        b.config(highlightbackground=C[colour], highlightthickness=2, highlightcolor=C[colour])
    return b


def make_label(parent, text, colour='text', font_key='body', **kwargs):
    """A styled label."""
    kwargs.setdefault('justify', 'left')
    kwargs.setdefault('anchor', 'w')
    return tk.Label(
        parent, text=text, bg=kwargs.pop('bg', C['bg']),
        fg=C[colour], font=FONTS[font_key], **kwargs
    )


def make_frame(parent, bg='bg', **kwargs):
    return tk.Frame(parent, bg=C[bg], **kwargs)


# =============================================================================
#  RICH-TEXT RENDERER
#  -- Converts the stage's plaintext "html" strings into nicely styled widgets.
#  -- Supports:
#       `inline code`
#       [TIP] / [WARN] / [QUEST] / [BOSS] callout blocks (line starts with token)
#       numbered lists (line starts with "  1. ", "  2. ", ...)
#       bullet lists (line starts with "  * ")
#       ``` code fences (block of code)
# =============================================================================
def render_rich_text(parent, text, width=900):
    """Render the rich-text into `parent` by adding child widgets."""
    if not text:
        return

    # Normalise
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]

        # --- Code fence block ```
        if line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code_block = tk.Frame(parent, bg=C['editor_bg'], bd=1, relief='flat',
                                  highlightbackground=C['border'], highlightthickness=1)
            code_block.pack(fill='x', pady=(4, 8), padx=2)
            tk.Label(code_block, text='\n'.join(code_lines), bg=C['editor_bg'],
                     fg=C['text'], font=FONTS['code'], justify='left',
                     anchor='w').pack(fill='x', padx=14, pady=10)
            continue

        stripped = line.lstrip()

        # --- Callouts: [TIP] / [WARN] / [QUEST] / [BOSS]
        callout_map = {
            '[TIP]':   ('neon_cyan',   'TIP'),
            '[WARN]':  ('neon_pink',   'WATCH OUT'),
            '[QUEST]': ('neon_yellow', 'MINI-QUEST'),
            '[BOSS]':  ('neon_orange', 'BOSS FIGHT'),
        }
        matched_callout = None
        for tag, info in callout_map.items():
            if stripped.startswith(tag):
                matched_callout = (tag, info)
                break
        if matched_callout:
            tag, (colour, label) = matched_callout
            body = stripped[len(tag):].strip()
            box = tk.Frame(parent, bg=C['bg_2'],
                           highlightbackground=C[colour], highlightthickness=0)
            box.pack(fill='x', pady=6, padx=2)
            # Left neon bar
            bar = tk.Frame(box, bg=C[colour], width=4)
            bar.pack(side='left', fill='y')
            inner = tk.Frame(box, bg=C['bg_2'])
            inner.pack(side='left', fill='both', expand=True, padx=10, pady=10)
            tk.Label(inner, text=f"{'[BOSS] ' if tag == '[BOSS]' else ''}{label}",
                     bg=C['bg_2'], fg=C[colour],
                     font=FONTS['arcade_xs']).pack(anchor='w')
            # Render the body (may span multiple lines starting with spaces)
            body_lines = [body]
            while i + 1 < len(lines) and (lines[i+1].startswith('  ') or lines[i+1].strip() == ''):
                # continuation line (indented) or blank separator
                nxt = lines[i+1]
                if nxt.strip() == '' and (i+2 >= len(lines) or not lines[i+2].startswith('  ')):
                    break
                i += 1
                body_lines.append(nxt.strip())
            full = ' '.join(b for b in body_lines if b).strip()
            _render_inline_paragraph(inner, full, bg=C['bg_2'], width=width - 40)
            i += 1
            continue

        # --- Numbered list "  1. ..." or "1. ..."
        m = re.match(r'^\s*(\d+)\.\s+(.*)$', line)
        if m:
            num, body = m.group(1), m.group(2)
            # Gather contiguous numbered items
            row = tk.Frame(parent, bg=C['bg'])
            row.pack(fill='x', padx=16)
            tk.Label(row, text=f"{num}.", bg=C['bg'], fg=C['neon_yellow'],
                     font=FONTS['body_bold'], width=3, anchor='nw').pack(side='left', anchor='n')
            txt_frame = tk.Frame(row, bg=C['bg'])
            txt_frame.pack(side='left', fill='x', expand=True)
            _render_inline_paragraph(txt_frame, body, bg=C['bg'], width=width - 60)
            i += 1
            continue

        # --- Bullet "  * ..."
        m = re.match(r'^\s*\*\s+(.*)$', line)
        if m:
            body = m.group(1)
            row = tk.Frame(parent, bg=C['bg'])
            row.pack(fill='x', padx=16)
            tk.Label(row, text='*', bg=C['bg'], fg=C['neon_cyan'],
                     font=FONTS['body_bold'], width=3, anchor='nw').pack(side='left', anchor='n')
            txt_frame = tk.Frame(row, bg=C['bg'])
            txt_frame.pack(side='left', fill='x', expand=True)
            _render_inline_paragraph(txt_frame, body, bg=C['bg'], width=width - 60)
            i += 1
            continue

        # --- Blank line
        if line.strip() == '':
            tk.Frame(parent, bg=C['bg'], height=4).pack()
            i += 1
            continue

        # --- Regular paragraph (may span several non-blank lines)
        para_lines = [line]
        while i + 1 < len(lines) and lines[i+1].strip() != '' and not _line_is_special(lines[i+1]):
            i += 1
            para_lines.append(lines[i])
        full = ' '.join(p.strip() for p in para_lines)
        _render_inline_paragraph(parent, full, bg=C['bg'], width=width)
        i += 1


def _line_is_special(line):
    """True if line starts a list, callout, or code fence."""
    s = line.lstrip()
    if s.startswith('```'):
        return True
    if s.startswith('['):
        for tag in ('[TIP]', '[WARN]', '[QUEST]', '[BOSS]'):
            if s.startswith(tag):
                return True
    if re.match(r'^\s*\d+\.\s+', line):
        return True
    if re.match(r'^\s*\*\s+', line):
        return True
    return False


def _render_inline_paragraph(parent, text, bg, width=900):
    """
    Render a paragraph, handling inline `code` (backticks) by swapping colour.
    Uses a tk.Text widget sized to content -- gives us inline styling + wrap.
    """
    # Use Text widget for flexible inline styling
    t = tk.Text(parent, bg=bg, fg=C['text'], font=FONTS['body'],
                wrap='word', bd=0, highlightthickness=0,
                padx=0, pady=2, cursor='arrow')
    t.tag_configure('code', foreground=C['neon_green'], background=C['bg_2'],
                    font=FONTS['code'])
    t.tag_configure('bold', font=FONTS['body_bold'])

    # Split on backticks; odd segments are code
    parts = re.split(r'`([^`]+)`', text)
    for idx, seg in enumerate(parts):
        if idx % 2 == 0:
            # regular text -- handle **bold** too
            bold_parts = re.split(r'\*\*([^*]+)\*\*', seg)
            for j, bp in enumerate(bold_parts):
                if j % 2 == 0:
                    t.insert('end', bp)
                else:
                    t.insert('end', bp, 'bold')
        else:
            t.insert('end', seg, 'code')

    t.config(state='disabled')
    # Auto-height: count wrapped lines after a moment
    t.pack(fill='x', anchor='w')
    parent.update_idletasks()
    # Set height based on content
    def adjust_height(widget=t):
        widget.config(state='normal')
        widget.update_idletasks()
        # Use display lines (respects word-wrap)
        end = widget.index('end-1c')
        last_line = int(end.split('.')[0])
        # Count display lines using the 'displaylines' method via dlineinfo
        widget.config(height=max(1, last_line))
        widget.config(state='disabled')
    adjust_height()



# =============================================================================
#  CODE PLAYGROUND WIDGET  (editor + RUN/RESET + output area)
# =============================================================================
class CodePlayground(tk.Frame):
    """A single code editor box with RUN and RESET buttons."""
    def __init__(self, parent, app, key, code_def):
        super().__init__(parent, bg=C['editor_bg'],
                         highlightbackground=C['neon_green'], highlightthickness=2)
        self.app = app
        self.key = key
        self.code_def = code_def

        # Header
        header = tk.Frame(self, bg=C['bg_2'])
        header.pack(fill='x')
        tk.Label(header, text=f"> {code_def['filename']}",
                 bg=C['bg_2'], fg=C['neon_green'],
                 font=FONTS['arcade_xs']).pack(side='left', padx=10, pady=6)

        btns = tk.Frame(header, bg=C['bg_2'])
        btns.pack(side='right', padx=6, pady=4)

        self.run_btn = neon_button(btns, '>  RUN', self.on_run, 'neon_green',
                                   font_key='arcade_xs', padx=10, pady=4)
        self.reset_btn = neon_button(btns, 'RESET', self.on_reset, 'neon_pink',
                                     style='outline', font_key='arcade_xs',
                                     padx=10, pady=4)
        self.reset_btn.pack(side='left', padx=3)
        self.run_btn.pack(side='left', padx=3)

        # Separator
        tk.Frame(self, bg=C['border'], height=1).pack(fill='x')

        # Editor
        initial = self.app.state['saved_code'].get(key, code_def['starter'])
        line_count = initial.count('\n') + 2
        editor_height = max(5, min(22, line_count))

        self.editor = tk.Text(
            self, bg=C['editor_bg'], fg=C['text'],
            insertbackground=C['neon_green'],
            font=FONTS['code'], wrap='none',
            height=editor_height, bd=0, padx=14, pady=10,
            undo=True, tabs=('1c',),
        )
        self.editor.insert('1.0', initial)
        self.editor.pack(fill='both', expand=True)

        # Tab key inserts 4 spaces
        self.editor.bind('<Tab>', self._on_tab)
        # Debounced auto-save
        self._save_job = None
        self.editor.bind('<KeyRelease>', self._queue_save)

        # Separator
        tk.Frame(self, bg=C['border'], height=1).pack(fill='x')

        # Output
        self.output = tk.Text(
            self, bg=C['output_bg'], fg=C['neon_green'],
            font=FONTS['code'], wrap='word',
            height=5, bd=0, padx=14, pady=10,
            state='disabled',
        )
        self.output.tag_configure('muted', foreground=C['dim'], font=FONTS['code'])
        self.output.tag_configure('error', foreground=C['neon_pink'])
        self.output.tag_configure('ok', foreground=C['neon_green'])
        self._set_output("> Click RUN to execute your code", muted=True)
        self.output.pack(fill='both', expand=True)

    def _on_tab(self, event):
        self.editor.insert('insert', '    ')
        return 'break'

    def _queue_save(self, event=None):
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._do_save)

    def _do_save(self):
        code = self.editor.get('1.0', 'end-1c')
        self.app.state['saved_code'][self.key] = code
        save_state(self.app.state)

    def _set_output(self, text, muted=False, error=False):
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        tag = 'muted' if muted else ('error' if error else 'ok')
        self.output.insert('1.0', text, tag)
        self.output.config(state='disabled', fg=C['neon_pink'] if error else C['neon_green'])

    def on_reset(self):
        if messagebox.askyesno("Reset code?",
                               "Reset this code back to the starter template?",
                               parent=self.app):
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', self.code_def['starter'])
            self._do_save()

    def on_run(self):
        code = self.editor.get('1.0', 'end-1c')
        self.app.state['saved_code'][self.key] = code
        save_state(self.app.state)

        # Temporarily disable RUN button
        self.run_btn.config(state='disabled', text='..RUNNING..')
        self._set_output("> Running...", muted=True)
        self.update_idletasks()

        # Collect inputs up-front (same approach as the web version)
        input_count = count_input_calls(code)
        prompts = extract_input_prompts(code)
        inputs_list = []

        if input_count > 0:
            if has_loop_with_input(code):
                example = next((p for p in prompts if p), 'your values')
                bulk = simpledialog.askstring(
                    "Input (loop detected)",
                    ("This code uses input() inside a loop.\n"
                     f"Enter ALL answers separated by commas or new lines.\n"
                     f"Example prompt: \"{example}\"\n\n"
                     "(e.g. for a loop that reads 5 numbers: 10, 20, 30, 40, 50)"),
                    parent=self.app,
                )
                if bulk is None:
                    self._set_output("Run cancelled.", muted=True)
                    self._finish_run()
                    return
                inputs_list = [s.strip() for s in re.split(r'[,\n]', bulk) if s.strip() != '']
            else:
                for k in range(input_count):
                    p = prompts[k] if k < len(prompts) else 'Input:'
                    val = simpledialog.askstring("Input", p or 'Input:', parent=self.app)
                    if val is None:
                        self._set_output("Run cancelled.", muted=True)
                        self._finish_run()
                        return
                    inputs_list.append(val)

        # Run the code
        input_iter = iter(inputs_list)

        def provider(prompt=""):
            try:
                return next(input_iter)
            except StopIteration:
                # Ask the user live if code demanded more inputs than we had
                extra = simpledialog.askstring(
                    "More input needed", prompt or "Input:", parent=self.app)
                return extra if extra is not None else ""

        ok, output = run_user_code(code, provider)

        if not output:
            output = "(no output -- your code ran but didn't print anything)"
            self._set_output(output, muted=True)
        elif ok:
            self._set_output(output.rstrip())
        else:
            self._set_output(output.rstrip(), error=True)

        self._finish_run()

    def _finish_run(self):
        self.run_btn.config(state='normal', text='>  RUN')


# =============================================================================
#  STAGE CHALLENGE WIDGET  (NEW FEATURE)
#  -- A "type your own code" box shown at the end of every Stage.
#  -- Picks one challenge at random from the level's bank.
#  -- Has its own RUN-and-CHECK button: runs the code, then compares the
#     output against the challenge's expectations and shows pass/fail.
# =============================================================================
class StageChallenge(tk.Frame):
    """A challenge editor: task description + empty editor + RUN+CHECK button."""
    def __init__(self, parent, app, level_id, stage_idx, challenge):
        super().__init__(parent, bg=C['card'],
                         highlightbackground=C['neon_orange'], highlightthickness=2)
        self.app = app
        self.challenge = challenge
        self.key = f"L{level_id}_S{stage_idx}_chal"

        # ---- Header bar -----------------------------------------------------
        header = tk.Frame(self, bg=C['neon_orange'])
        header.pack(fill='x')
        tk.Label(header,
                 text=f"  [STAGE CHALLENGE] {challenge['task']}",
                 bg=C['neon_orange'], fg=C['bg'],
                 font=FONTS['arcade_xs'], anchor='w', padx=10, pady=6
                 ).pack(side='left', fill='x', expand=True)
        # "Refresh" button -- pick another random challenge
        refresh_btn = tk.Button(
            header, text='SHUFFLE',
            bg=C['neon_orange'], fg=C['bg'],
            activebackground=C['neon_yellow'], activeforeground=C['bg'],
            font=FONTS['arcade_xxs'],
            bd=0, relief='flat', cursor='hand2',
            padx=8, pady=4,
            command=self._on_shuffle,
        )
        refresh_btn.pack(side='right', padx=6, pady=4)

        # ---- Description ----------------------------------------------------
        desc_box = tk.Frame(self, bg=C['bg_2'])
        desc_box.pack(fill='x')
        tk.Label(desc_box, text=challenge['desc'],
                 bg=C['bg_2'], fg=C['text'],
                 font=FONTS['body'], justify='left', anchor='w',
                 wraplength=850, padx=14, pady=10).pack(fill='x', anchor='w')

        # ---- Buttons row ----------------------------------------------------
        btn_row = tk.Frame(self, bg=C['card'])
        btn_row.pack(fill='x', padx=10, pady=(8, 4))

        self.run_btn = neon_button(btn_row, '> RUN + CHECK', self.on_run_check,
                                   'neon_green', font_key='arcade_xs',
                                   padx=10, pady=4)
        self.run_btn.pack(side='left', padx=2)

        self.reset_btn = neon_button(btn_row, 'RESET', self.on_reset,
                                     'neon_pink', style='outline',
                                     font_key='arcade_xs',
                                     padx=10, pady=4)
        self.reset_btn.pack(side='left', padx=2)

        self.hint_btn = neon_button(btn_row, 'HINT', self.on_hint,
                                    'neon_yellow', style='outline',
                                    font_key='arcade_xs',
                                    padx=10, pady=4)
        self.hint_btn.pack(side='left', padx=2)

        # ---- Editor ---------------------------------------------------------
        starter = self.app.state['saved_code'].get(self.key, challenge['starter'])
        line_count = max(6, starter.count('\n') + 3)
        self.editor = tk.Text(
            self, bg=C['editor_bg'], fg=C['text'],
            insertbackground=C['neon_orange'],
            font=FONTS['code'], wrap='none',
            height=min(14, line_count), bd=0, padx=14, pady=10,
            undo=True, tabs=('1c',),
        )
        self.editor.insert('1.0', starter)
        self.editor.pack(fill='both', expand=True, padx=2, pady=(2, 0))
        self.editor.bind('<Tab>', self._on_tab)
        self._save_job = None
        self.editor.bind('<KeyRelease>', self._queue_save)

        # ---- Output ---------------------------------------------------------
        self.output = tk.Text(
            self, bg=C['output_bg'], fg=C['neon_green'],
            font=FONTS['code'], wrap='word',
            height=5, bd=0, padx=14, pady=10,
            state='disabled',
        )
        self.output.tag_configure('muted', foreground=C['dim'])
        self.output.tag_configure('error', foreground=C['neon_pink'])
        self.output.tag_configure('ok', foreground=C['neon_green'])
        self.output.tag_configure('pass', foreground=C['neon_green'],
                                  font=FONTS['mono_bold'])
        self.output.tag_configure('fail', foreground=C['neon_yellow'],
                                  font=FONTS['mono_bold'])
        self._set_output("> Type your answer above, then click RUN + CHECK", muted=True)
        self.output.pack(fill='both', expand=True, padx=2, pady=(0, 2))

    # -------------------------------------------------------------------------
    def _on_tab(self, event):
        self.editor.insert('insert', '    ')
        return 'break'

    def _queue_save(self, event=None):
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._do_save)

    def _do_save(self):
        code = self.editor.get('1.0', 'end-1c')
        self.app.state['saved_code'][self.key] = code
        save_state(self.app.state)

    def _set_output(self, text, muted=False, error=False, tag=None):
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        if tag:
            self.output.insert('1.0', text, tag)
        else:
            t = 'muted' if muted else ('error' if error else 'ok')
            self.output.insert('1.0', text, t)
        self.output.config(state='disabled',
                           fg=C['neon_pink'] if error else C['neon_green'])

    # -------------------------------------------------------------------------
    def on_reset(self):
        if messagebox.askyesno("Reset challenge?",
                               "Wipe what you've typed and start over?",
                               parent=self.app):
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', self.challenge['starter'])
            self._do_save()
            self._set_output("> Type your answer above, then click RUN + CHECK",
                             muted=True)

    def on_hint(self):
        hint = self.challenge.get('hint', '(no hint provided)')
        messagebox.showinfo("HINT", hint, parent=self.app)

    def _on_shuffle(self):
        # Pick another random challenge from this level and rebuild the widget
        # in place by asking the level view to re-render it.
        if hasattr(self.app, 'shuffle_stage_challenge'):
            self.app.shuffle_stage_challenge(self)

    # -------------------------------------------------------------------------
    def on_run_check(self):
        code = self.editor.get('1.0', 'end-1c')
        self._do_save()

        self.run_btn.config(state='disabled', text='..RUNNING..')
        self._set_output("> Running...", muted=True)
        self.update_idletasks()

        # Collect any input() prompts up-front
        input_count = count_input_calls(code)
        prompts = extract_input_prompts(code)
        inputs_list = []
        if input_count > 0:
            for k in range(input_count):
                p = prompts[k] if k < len(prompts) else 'Input:'
                val = simpledialog.askstring("Input", p or 'Input:', parent=self.app)
                if val is None:
                    self._set_output("Run cancelled.", muted=True)
                    self._finish()
                    return
                inputs_list.append(val)

        input_iter = iter(inputs_list)

        def provider(prompt=""):
            try:
                return next(input_iter)
            except StopIteration:
                extra = simpledialog.askstring(
                    "More input needed", prompt or "Input:", parent=self.app)
                return extra if extra is not None else ""

        ok, output = run_user_code(code, provider)

        # Decide pass / fail
        if not ok:
            # Code crashed -> show the traceback as a fail
            self._set_output(
                "[X] FAIL -- your code crashed.\n\n" + (output.rstrip() or "(no output)"),
                error=True)
        else:
            passed, message = check_challenge_output(self.challenge, output)
            display_out = output.rstrip() if output else "(no output)"
            if passed:
                # Header + output in two parts
                self.output.config(state='normal')
                self.output.delete('1.0', 'end')
                self.output.insert('end',
                                   f"[OK] PASSED!  {message}\n\n", 'pass')
                self.output.insert('end', "Your output:\n", 'muted')
                self.output.insert('end', display_out, 'ok')
                self.output.config(state='disabled', fg=C['neon_green'])
            else:
                self.output.config(state='normal')
                self.output.delete('1.0', 'end')
                self.output.insert('end',
                                   f"[X] NOT YET.  {message}\n\n", 'fail')
                self.output.insert('end', "Your output was:\n", 'muted')
                self.output.insert('end', display_out, 'ok')
                self.output.insert('end',
                                   "\n\nClick HINT for help, then try again.",
                                   'muted')
                self.output.config(state='disabled', fg=C['neon_yellow'])

        self._finish()

    def _finish(self):
        self.run_btn.config(state='normal', text='> RUN + CHECK')



# =============================================================================
#  MAIN APP
# =============================================================================
class PythonQuest(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PYTHON QUEST :: COMP1005 Game Mode")
        self.geometry("1120x780")
        self.minsize(900, 600)
        self.configure(bg=C['bg'])

        init_fonts()

        # State
        self.state = load_state()
        self.max_xp = sum(l['xp'] for l in LEVELS)
        self.current_level_id = None

        # Build outer layout: HUD on top, main scrollable area below
        self._build_hud()

        self.main_area = ScrollableFrame(self)
        self.main_area.pack(fill='both', expand=True)

        # Toast notification (hidden until shown)
        self.toast_label = tk.Label(
            self, text='', bg=C['bg_2'], fg=C['neon_yellow'],
            font=FONTS['arcade_sm'],
            padx=20, pady=12,
            highlightbackground=C['neon_yellow'], highlightthickness=2,
        )
        # We'll place()/place_forget() it when toasting
        self._toast_after_id = None

        # Start on the map
        self.show_map()

        # Save on close
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_close(self):
        save_state(self.state)
        self.destroy()

    # -------------------------------------------------------------------------
    #  HUD  (top bar - persistent)
    # -------------------------------------------------------------------------
    def _build_hud(self):
        self.hud = tk.Frame(self, bg=C['bg_2'],
                            highlightbackground=C['neon_green'],
                            highlightthickness=2)
        self.hud.pack(fill='x', padx=10, pady=(10, 4))

        inner = tk.Frame(self.hud, bg=C['bg_2'])
        inner.pack(fill='x', padx=16, pady=12)

        title_row = tk.Frame(inner, bg=C['bg_2'])
        title_row.pack(fill='x', anchor='w')
        self.title_label = tk.Label(
            title_row, text='> PYTHON QUEST_',
            bg=C['bg_2'], fg=C['neon_green'],
            font=FONTS['arcade_xl'],
        )
        self.title_label.pack(side='left')
        self._blink_on = True
        self._blink_cursor()

        # Stats row
        stats = tk.Frame(inner, bg=C['bg_2'])
        stats.pack(fill='x', pady=(8, 0))
        stats.columnconfigure(0, weight=1, uniform='stats')
        stats.columnconfigure(1, weight=1, uniform='stats')
        stats.columnconfigure(2, weight=1, uniform='stats')
        stats.columnconfigure(3, weight=1, uniform='stats')

        self.rank_val = self._build_stat_card(stats, 0, 'RANK', 'NOVICE', 'neon_green')
        self.xp_val = self._build_stat_card(stats, 1, 'TOTAL XP', '0', 'neon_yellow')
        self.cleared_val = self._build_stat_card(stats, 2, 'CLEARED',
                                                 f'0 / {len(LEVELS)}', 'neon_pink')
        self.mode_val = self._build_stat_card(stats, 3, 'MODE', 'WEEK 10', 'neon_cyan')

        # XP bar
        bar_frame = tk.Frame(inner, bg='#000033', height=10,
                             highlightbackground=C['border'], highlightthickness=1)
        bar_frame.pack(fill='x', pady=(10, 2))
        bar_frame.pack_propagate(False)
        self.xp_fill = tk.Frame(bar_frame, bg=C['neon_yellow'], height=10)
        self.xp_fill.place(relx=0, rely=0, relheight=1, relwidth=0)

        self._update_hud()

    def _build_stat_card(self, parent, col, label, value, colour):
        card = tk.Frame(parent, bg=C['bg'],
                        highlightbackground=C[colour], highlightthickness=0)
        card.grid(row=0, column=col, padx=4, sticky='ew')
        bar = tk.Frame(card, bg=C[colour], width=3)
        bar.pack(side='left', fill='y')
        inner = tk.Frame(card, bg=C['bg'])
        inner.pack(side='left', fill='both', expand=True, padx=10, pady=6)
        tk.Label(inner, text=label, bg=C['bg'], fg=C['dim'],
                 font=FONTS['arcade_xxs']).pack(anchor='w')
        val = tk.Label(inner, text=value, bg=C['bg'], fg=C[colour],
                       font=FONTS['arcade_sm'])
        val.pack(anchor='w')
        return val

    def _blink_cursor(self):
        t = self.title_label.cget('text')
        if t.endswith('_'):
            self.title_label.config(text=t[:-1] + ' ')
        else:
            self.title_label.config(text=t[:-1] + '_')
        self.after(700, self._blink_cursor)

    def _update_hud(self):
        self.rank_val.config(text=get_rank(self.state['xp']))
        self.xp_val.config(text=str(self.state['xp']))
        self.cleared_val.config(text=f"{len(self.state['cleared'])} / {len(LEVELS)}")
        pct = 0 if self.max_xp == 0 else min(1.0, self.state['xp'] / self.max_xp)
        self.xp_fill.place_configure(relwidth=pct)

    # -------------------------------------------------------------------------
    #  VIEW: LEVEL MAP  (intro + week plan + level grid)
    # -------------------------------------------------------------------------
    def show_map(self):
        self.current_level_id = None
        self._clear_main()
        wrap = tk.Frame(self.main_area.inner, bg=C['bg'])
        wrap.pack(fill='both', expand=True, padx=20, pady=20)

        # --- Intro box ---
        intro = tk.Frame(wrap, bg=C['bg_2'],
                         highlightbackground=C['neon_pink'], highlightthickness=2)
        intro.pack(fill='x', pady=(0, 14))
        intro_inner = tk.Frame(intro, bg=C['bg_2'])
        intro_inner.pack(fill='x', padx=18, pady=14)
        tk.Label(intro_inner, text='> WELCOME, PLAYER ONE',
                 bg=C['bg_2'], fg=C['neon_pink'],
                 font=FONTS['arcade_lg']).pack(anchor='w', pady=(0, 10))
        for paragraph in [
            "This is your COMP1005 live-code training ground. Every code block below is a "
            "real editor -- type Python, hit RUN, see output. Running natively on your "
            "machine -- fast!",
            "You're in Week 10 (20 Apr 2026). Prac Test 4 hits next week -- covers Pracs 6 "
            "& 7. Levels 6 & 7 have the deepest content.",
        ]:
            lbl = tk.Label(intro_inner, text=paragraph, bg=C['bg_2'], fg=C['text'],
                           font=FONTS['body'], wraplength=1000, justify='left', anchor='w')
            lbl.pack(fill='x', anchor='w', pady=3)

        # ADHD tip
        tip = tk.Frame(intro_inner, bg='#2a2800',
                       highlightbackground=C['neon_yellow'], highlightthickness=0)
        tip.pack(fill='x', pady=(8, 0))
        tb = tk.Frame(tip, bg=C['neon_yellow'], width=3)
        tb.pack(side='left', fill='y')
        ti = tk.Frame(tip, bg='#2a2800')
        ti.pack(side='left', fill='both', expand=True, padx=10, pady=8)
        tk.Label(ti, text=("ADHD-FRIENDLY PLAN: One level per sitting (~20-40 min). "
                           "Progress auto-saves. Code boxes remember what you typed, "
                           "even after closing the app."),
                 bg='#2a2800', fg=C['neon_yellow'], font=FONTS['body'],
                 wraplength=1000, justify='left', anchor='w').pack(fill='x', anchor='w')

        # --- Week plan ---
        plan = tk.Frame(wrap, bg=C['card'],
                        highlightbackground=C['neon_orange'], highlightthickness=2)
        plan.pack(fill='x', pady=(0, 20))
        plan_inner = tk.Frame(plan, bg=C['card'])
        plan_inner.pack(fill='x', padx=18, pady=14)
        tk.Label(plan_inner, text='YOUR 7-DAY BATTLE PLAN (to Prac Test 4)',
                 bg=C['card'], fg=C['neon_orange'],
                 font=FONTS['arcade_md']).pack(anchor='w', pady=(0, 10))
        plan_items = [
            ("Today (Mon 20 Apr):", "Levels 1 & 2 warm-up. ~45 min."),
            ("Tue 21 Apr:",          "Levels 3 & 4 (arrays, functions). ~45 min."),
            ("Wed 22 Apr:",          "Level 5 (files) + start Level 6. ~60 min."),
            ("Thu 23 Apr:",          "Level 6 -- Objects. The big one. ~60 min."),
            ("Fri 24 Apr:",          "Level 7 -- Inheritance & Exceptions. ~60 min."),
            ("Sat 25 Apr:",          "Levels 8 + 9 + 10 + 11 (lighter content)."),
            ("Sun 26 Apr:",          "Re-do Boss quizzes for Levels 6 & 7. Rest."),
        ]
        for i, (day, what) in enumerate(plan_items, 1):
            row = tk.Frame(plan_inner, bg=C['card'])
            row.pack(fill='x', pady=2)
            tk.Label(row, text=f"{i}.", bg=C['card'], fg=C['neon_orange'],
                     font=FONTS['body_bold'], width=3).pack(side='left', anchor='n')
            tk.Label(row, text=day, bg=C['card'], fg=C['neon_yellow'],
                     font=FONTS['body_bold']).pack(side='left')
            tk.Label(row, text=' ' + what, bg=C['card'], fg=C['text'],
                     font=FONTS['body']).pack(side='left')

        # --- Level grid header ---
        tk.Label(wrap, text='> SELECT LEVEL',
                 bg=C['bg'], fg=C['neon_cyan'],
                 font=FONTS['arcade_md']).pack(anchor='w', pady=(4, 10))

        # --- Level grid ---
        grid = tk.Frame(wrap, bg=C['bg'])
        grid.pack(fill='x')
        COLS = 2
        for c in range(COLS):
            grid.columnconfigure(c, weight=1, uniform='levels')

        first_uncleared = next((l for l in LEVELS if l['id'] not in self.state['cleared']), None)
        current_id = first_uncleared['id'] if first_uncleared else None

        for idx, lvl in enumerate(LEVELS):
            done = lvl['id'] in self.state['cleared']
            prev = LEVELS[idx - 1] if idx > 0 else None
            locked = (not done and prev is not None
                      and prev['id'] not in self.state['cleared']
                      and lvl['id'] != current_id)
            is_current = (lvl['id'] == current_id and not done)

            r, c = divmod(idx, COLS)
            self._build_level_card(grid, lvl, done, locked, is_current).grid(
                row=r, column=c, padx=7, pady=7, sticky='nsew')

        # --- Reset button ---
        tk.Frame(wrap, bg=C['bg'], height=14).pack()
        reset = neon_button(wrap, 'RESET ALL PROGRESS', self.reset_game,
                            'dim', style='outline',
                            font_key='arcade_xs', padx=10, pady=6)
        reset.config(highlightbackground=C['dim'], fg=C['dim'])
        reset.pack(anchor='w')

        self.main_area.scroll_to_top()

    def _build_level_card(self, parent, lvl, done, locked, is_current):
        # Border colour depends on state
        border_colour = (C['neon_green'] if done
                         else C['neon_yellow'] if is_current
                         else C['border'])

        card = tk.Frame(parent, bg=C['card'],
                        highlightbackground=border_colour, highlightthickness=2,
                        cursor='hand2' if not locked else 'arrow')
        inner = tk.Frame(card, bg=C['card'])
        inner.pack(fill='both', expand=True, padx=14, pady=12)

        # Top row: level number + cleared badge
        top = tk.Frame(inner, bg=C['card'])
        top.pack(fill='x')
        tk.Label(top, text=f"LVL {lvl['id']} / {lvl['num']}",
                 bg=C['card'], fg=C['neon_pink'],
                 font=FONTS['arcade_xs']).pack(side='left')
        if done:
            tk.Label(top, text='CLEARED', bg=C['card'], fg=C['neon_green'],
                     font=FONTS['arcade_xxs'],
                     padx=6, pady=2).pack(side='right')
        elif is_current:
            tk.Label(top, text='<< NEXT', bg=C['card'], fg=C['neon_yellow'],
                     font=FONTS['arcade_xxs'],
                     padx=6, pady=2).pack(side='right')
        elif locked:
            tk.Label(top, text='LOCKED', bg=C['card'], fg=C['dim'],
                     font=FONTS['arcade_xxs'],
                     padx=6, pady=2).pack(side='right')

        # Title
        tk.Label(inner, text=lvl['title'], bg=C['card'], fg=C['text'],
                 font=FONTS['body_bold'], anchor='w', justify='left',
                 wraplength=460).pack(anchor='w', pady=(6, 4))
        # Desc
        tk.Label(inner, text=lvl['desc'], bg=C['card'], fg=C['dim'],
                 font=FONTS['body'], anchor='w', justify='left',
                 wraplength=460).pack(anchor='w', pady=(0, 6))
        # Meta
        meta = tk.Frame(inner, bg=C['card'])
        meta.pack(fill='x', pady=(2, 4))
        tk.Label(meta, text=f"{len(lvl['stages'])} stages",
                 bg=C['card'], fg=C['neon_cyan'],
                 font=FONTS['mono_sm']).pack(side='left')
        tk.Label(meta, text=f"+{lvl['xp']} XP",
                 bg=C['card'], fg=C['neon_yellow'],
                 font=FONTS['mono_sm']).pack(side='right')

        # Badges
        badges = tk.Frame(inner, bg=C['card'])
        badges.pack(fill='x', pady=(6, 0))
        for b in lvl['badges']:
            badge = tk.Label(badges, text=b, bg='#001018', fg=C['neon_cyan'],
                             font=FONTS['arcade_xxs'],
                             padx=5, pady=3,
                             highlightbackground=C['neon_cyan'], highlightthickness=1)
            badge.pack(side='left', padx=2, pady=2)

        # Locked overlay effect (dim everything)
        if locked:
            for w in self._all_descendants(card):
                try:
                    if isinstance(w, tk.Label):
                        w.config(fg=C['locked'])
                except Exception:
                    pass

        # Click binding (on card and ALL descendants -- any click opens it)
        if not locked:
            def _open(event=None, lid=lvl['id']):
                self.open_level(lid)
            for w in [card] + self._all_descendants(card):
                w.bind('<Button-1>', _open)
                try:
                    w.config(cursor='hand2')
                except Exception:
                    pass

        return card

    def _all_descendants(self, widget):
        result = []
        for child in widget.winfo_children():
            result.append(child)
            result.extend(self._all_descendants(child))
        return result

    def _clear_main(self):
        for child in self.main_area.inner.winfo_children():
            child.destroy()

    # -------------------------------------------------------------------------
    #  VIEW: LEVEL DETAIL
    # -------------------------------------------------------------------------
    def open_level(self, level_id):
        self.current_level_id = level_id
        lvl = next((l for l in LEVELS if l['id'] == level_id), None)
        if lvl is None:
            return
        done = level_id in self.state['cleared']

        self._clear_main()
        # Reset the per-level tracker for stage-challenge widgets
        # (used by the SHUFFLE button on each challenge).
        self._stage_challenge_widgets = []
        wrap = tk.Frame(self.main_area.inner, bg=C['bg'])
        wrap.pack(fill='both', expand=True, padx=20, pady=20)

        # --- Detail header (title + back button) ---
        header_box = tk.Frame(wrap, bg=C['bg_2'],
                              highlightbackground=C['neon_green'], highlightthickness=2)
        header_box.pack(fill='x', pady=(0, 14))
        hh = tk.Frame(header_box, bg=C['bg_2'])
        hh.pack(fill='x', padx=16, pady=14)

        tk.Label(hh, text=f"LVL {lvl['id']} - {lvl['title']}",
                 bg=C['bg_2'], fg=C['neon_green'],
                 font=FONTS['arcade_md'], anchor='w',
                 wraplength=850, justify='left').pack(side='left', fill='x', expand=True)
        back = neon_button(hh, '< MAP', self.show_map, 'neon_pink',
                           style='outline', font_key='arcade_xs',
                           padx=12, pady=6)
        back.pack(side='right', padx=(10, 0))

        # --- Stages ---
        for i, stage in enumerate(lvl['stages']):
            self._build_stage(wrap, lvl, stage, i)

        # --- Quiz ---
        self._build_quiz(wrap, lvl)

        # --- Complete button ---
        self.complete_btn = neon_button(
            wrap,
            (' RE-CLEAR (already cleared) ' if done
             else f"CLEAR THIS LEVEL -> +{lvl['xp']} XP"),
            lambda lid=lvl['id']: self.clear_level(lid),
            'neon_green', font_key='arcade_md', padx=20, pady=14,
        )
        self.complete_btn.config(state='disabled')
        self.complete_btn.pack(fill='x', pady=(20, 0))

        self.main_area.scroll_to_top()

    def _build_stage(self, parent, lvl, stage, stage_idx):
        stage_frame = tk.Frame(parent, bg=C['card'])
        stage_frame.pack(fill='x', pady=(0, 10))
        # Left neon cyan bar
        tk.Frame(stage_frame, bg=C['neon_cyan'], width=4).pack(side='left', fill='y')
        inner = tk.Frame(stage_frame, bg=C['card'])
        inner.pack(side='left', fill='both', expand=True, padx=16, pady=14)

        # Stage number tag
        tag = tk.Label(inner,
                       text=f"STAGE {stage_idx+1:02d} / {len(lvl['stages']):02d}",
                       bg=C['neon_cyan'], fg=C['bg'],
                       font=FONTS['arcade_xxs'], padx=6, pady=3)
        tag.pack(anchor='w')

        # Title
        tk.Label(inner, text=stage['title'], bg=C['card'], fg=C['neon_cyan'],
                 font=FONTS['body_bold'], anchor='w',
                 wraplength=900, justify='left').pack(anchor='w', pady=(8, 8))

        # Intro HTML
        if stage.get('html'):
            render_rich_text(inner, stage['html'])

        # First code box
        if stage.get('code'):
            key = f"L{lvl['id']}_S{stage_idx}"
            cp = CodePlayground(inner, self, key, stage['code'])
            cp.pack(fill='x', pady=10)

        # After-HTML
        if stage.get('afterHtml'):
            render_rich_text(inner, stage['afterHtml'])

        # Second code box
        if stage.get('code2'):
            key = f"L{lvl['id']}_S{stage_idx}_b"
            cp2 = CodePlayground(inner, self, key, stage['code2'])
            cp2.pack(fill='x', pady=10)

        if stage.get('afterHtml2'):
            render_rich_text(inner, stage['afterHtml2'])

        # ---- Stage Challenge ---------------------------------------------
        # Pick one of the level's challenges at random -- BUT only from the
        # pool of challenges whose required content has already been taught
        # up to and including THIS stage. Guarantees the student never meets
        # a challenge whose concepts haven't been introduced yet.
        challenge = pick_stage_challenge(lvl['id'], current_stage_idx=stage_idx)
        if challenge:
            sc = StageChallenge(inner, self, lvl['id'], stage_idx, challenge)
            sc.pack(fill='x', pady=(14, 4))
            # Track widgets so SHUFFLE can rebuild them in place
            if not hasattr(self, '_stage_challenge_widgets'):
                self._stage_challenge_widgets = []
            self._stage_challenge_widgets.append(
                {'widget': sc, 'parent': inner, 'level_id': lvl['id'],
                 'stage_idx': stage_idx}
            )

    # -------------------------------------------------------------------------
    #  STAGE CHALLENGE -- shuffle (re-pick a random challenge in place)
    # -------------------------------------------------------------------------
    def shuffle_stage_challenge(self, current_widget):
        """Replace the given StageChallenge with a freshly-picked one."""
        record = next(
            (r for r in getattr(self, '_stage_challenge_widgets', [])
             if r['widget'] is current_widget),
            None
        )
        if record is None:
            return
        new_challenge = pick_stage_challenge(
            record['level_id'],
            current_stage_idx=record['stage_idx'],
        )
        if not new_challenge:
            return
        # Build the replacement BEFORE destroying the old, so the layout
        # remains stable.
        new_widget = StageChallenge(
            record['parent'], self,
            record['level_id'], record['stage_idx'],
            new_challenge,
        )
        new_widget.pack(fill='x', pady=(14, 4))
        current_widget.destroy()
        record['widget'] = new_widget

    # -------------------------------------------------------------------------
    #  QUIZ
    # -------------------------------------------------------------------------
    def _build_quiz(self, parent, lvl):
        # NEW: pick one of the 7 quiz variations for this level at random.
        # Falls back to the level's default 'quiz' if no variations exist.
        quiz = pick_quiz_variation(lvl['id'], lvl['quiz'])
        # Stash so _quiz_click uses the SAME quiz the user is looking at.
        self._current_quiz = quiz

        quiz_box = tk.Frame(parent, bg=C['card'],
                            highlightbackground=C['neon_pink'], highlightthickness=2)
        quiz_box.pack(fill='x', pady=10)
        inner = tk.Frame(quiz_box, bg=C['card'])
        inner.pack(fill='x', padx=18, pady=14)

        # Header row: title + "shuffle quiz" button
        head = tk.Frame(inner, bg=C['card'])
        head.pack(fill='x', pady=(0, 10))
        tk.Label(head, text='[!] BOSS QUIZ',
                 bg=C['card'], fg=C['neon_pink'],
                 font=FONTS['arcade_md']).pack(side='left')
        # SHUFFLE button -- pick another of the 7 variations
        shuffle_quiz_btn = neon_button(
            head, 'SHUFFLE', lambda l=lvl: self._shuffle_quiz(l),
            'neon_yellow', style='outline',
            font_key='arcade_xxs', padx=8, pady=4,
        )
        shuffle_quiz_btn.pack(side='right')
        self._quiz_box_ref = quiz_box  # remember for shuffle

        # Question (preformatted)
        q_frame = tk.Frame(inner, bg=C['editor_bg'])
        q_frame.pack(fill='x', pady=(0, 10))
        tk.Label(q_frame, text=quiz['q'],
                 bg=C['editor_bg'], fg=C['text'],
                 font=FONTS['code'],
                 justify='left', anchor='w',
                 padx=12, pady=10).pack(fill='x', anchor='w')

        # Options
        self._quiz_answered = False
        self._quiz_option_buttons = []
        opts_frame = tk.Frame(inner, bg=C['card'])
        opts_frame.pack(fill='x', pady=4)
        for i, opt in enumerate(quiz['options']):
            txt = f"{chr(65 + i)}) {opt}"
            btn = tk.Button(
                opts_frame, text=txt,
                bg=C['bg'], fg=C['text'],
                activebackground=C['card_hover'],
                activeforeground=C['text'],
                font=FONTS['body'], anchor='w', justify='left',
                padx=14, pady=10, bd=0, relief='flat', cursor='hand2',
                wraplength=900,
                highlightbackground=C['border'], highlightthickness=2,
                command=lambda idx=i, q=quiz: self._quiz_click(idx, q),
            )
            btn.pack(fill='x', pady=4)
            self._quiz_option_buttons.append(btn)

        # Feedback placeholder
        self.quiz_feedback = tk.Label(inner, text='', bg=C['card'],
                                      fg=C['text'], font=FONTS['body'],
                                      wraplength=900, justify='left', anchor='w')

    def _shuffle_quiz(self, lvl):
        """Replace the current quiz with another random variation."""
        # Find the parent that holds the quiz box (the wrap frame above it).
        quiz_box = getattr(self, '_quiz_box_ref', None)
        if quiz_box is None:
            return
        parent = quiz_box.master
        # Where in the pack order is the quiz? It's between the stages and the
        # Complete button. Easiest fix: destroy the old box, build a new one,
        # and re-pack the Complete button after it so order stays correct.
        complete_btn = getattr(self, 'complete_btn', None)
        complete_was_enabled = (complete_btn is not None
                                and str(complete_btn['state']) == 'normal')
        quiz_box.destroy()
        self._build_quiz(parent, lvl)
        # The new quiz answers reset, so we re-disable the Complete button
        # UNLESS the level is already cleared.
        if complete_btn is not None and not complete_was_enabled:
            complete_btn.config(state='disabled')
        # Move the Complete button back to the bottom.
        if complete_btn is not None:
            complete_btn.pack_forget()
            complete_btn.pack(fill='x', pady=(20, 0))

    def _quiz_click(self, chosen_idx, quiz):
        if self._quiz_answered:
            return
        self._quiz_answered = True
        correct_idx = quiz['correct']
        for i, btn in enumerate(self._quiz_option_buttons):
            btn.config(state='disabled')
            if i == correct_idx:
                btn.config(bg='#0f2a0f', fg=C['neon_green'],
                           highlightbackground=C['neon_green'])
            elif i == chosen_idx:
                btn.config(bg='#2a0f1f', fg=C['neon_pink'],
                           highlightbackground=C['neon_pink'])

        if chosen_idx == correct_idx:
            self.quiz_feedback.config(
                text="[OK] CORRECT! " + quiz['explain'],
                fg=C['neon_green'])
        else:
            self.quiz_feedback.config(
                text="[X] Not quite. " + quiz['explain'],
                fg=C['neon_pink'])
        self.quiz_feedback.pack(fill='x', pady=(10, 0))

        # Unlock the "clear level" button
        self.complete_btn.config(state='normal')

    # -------------------------------------------------------------------------
    #  CLEAR LEVEL / RESET / TOAST
    # -------------------------------------------------------------------------
    def clear_level(self, level_id):
        lvl = next(l for l in LEVELS if l['id'] == level_id)
        was_cleared = level_id in self.state['cleared']
        if not was_cleared:
            self.state['cleared'].append(level_id)
            self.state['xp'] += lvl['xp']
            save_state(self.state)
            self.show_toast(f"LEVEL {level_id} CLEARED! +{lvl['xp']} XP")
        else:
            self.show_toast(f"LEVEL {level_id} REVIEWED")
        self._update_hud()
        self.after(900, self.show_map)

    def reset_game(self):
        if not messagebox.askyesno(
                "Reset?", "Wipe all progress (including saved code) and start over?",
                parent=self):
            return
        self.state = dict(DEFAULT_STATE)
        self.state['saved_code'] = {}
        save_state(self.state)
        self._update_hud()
        self.show_map()

    def show_toast(self, msg):
        if self._toast_after_id is not None:
            try:
                self.after_cancel(self._toast_after_id)
            except Exception:
                pass
        self.toast_label.config(text=msg)
        self.toast_label.place(relx=0.5, rely=1.0, anchor='s', y=-30)
        self._toast_after_id = self.after(2400, self._hide_toast)

    def _hide_toast(self):
        self.toast_label.place_forget()


# =============================================================================
#  LAUNCH
# =============================================================================
def main():
    app = PythonQuest()
    app.mainloop()


if __name__ == '__main__':
    main()
