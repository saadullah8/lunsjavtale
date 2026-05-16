import os
print("Running makemigrations scm...")
os.system("python manage.py makemigrations scm")
print("Running migrate scm...")
os.system("python manage.py migrate scm")
print("Done!")
