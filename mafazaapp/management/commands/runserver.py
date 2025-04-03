from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management.commands.runserver import BaseRunserverCommand
from django.core.management.base import BaseCommand
from django.core.servers import basehttp
from django.core.servers.basehttp import WSGIServer
import socket
import sys

class Command(RunserverCommand):
    help = 'Runs the development server with HTTP only'

    def handle(self, *args, **options):
        """Override the handle method to ensure HTTP only."""
        self.stdout.write('Starting development server with HTTP only...')
        super().handle(*args, **options)

    def inner_run(self, *args, **options):
        """Override the inner_run method to ensure HTTP only."""
        try:
            handler = self.get_handler(*args, **options)
            run(self.inner_run_cmd, options, handler)
        except KeyboardInterrupt:
            self.stdout.write('\nShutting down...')
            sys.exit(0)

    def inner_run_cmd(self, *args, **options):
        """Override the inner_run_cmd method to ensure HTTP only."""
        try:
            handler = self.get_handler(*args, **options)
            run(self.inner_run_cmd, options, handler)
        except KeyboardInterrupt:
            self.stdout.write('\nShutting down...')
            sys.exit(0)

def run(inner_run, options, handler):
    """Override the run method to ensure HTTP only."""
    try:
        inner_run(options, handler)
    except KeyboardInterrupt:
        sys.exit(0) 