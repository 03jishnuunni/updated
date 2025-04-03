web: gunicorn mafaza__project.wsgi --log-file - 
#or works good with external database
web: python manage.py migrate && gunicorn mafaza__project.wsgi