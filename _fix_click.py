with open("index.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Replace line 782 (index 781) with the expanded version
old_line = lines[781]
new_lines = [
    "document.addEventListener('click',function(e){\n",
    "  if(!e.target.closest('.cat-dropdown')){\n",
    "    document.getElementById('catMenu').classList.remove('open');\n",
    "    document.querySelector('#catDropdown .cat-dropdown-trigger').classList.remove('open');\n",
    "  }\n",
    "  if(!e.target.closest('#editCatDropdown')){\n",
    "    document.getElementById('editCatMenu').classList.remove('open');\n",
    "    document.getElementById('editCatTrigger').classList.remove('open');\n",
    "  }\n",
    "});\n",
]

# Replace line 782
lines[781:782] = new_lines

with open("index.html", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Click handler updated")
