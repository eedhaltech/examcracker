import io
from django.core.management.base import BaseCommand, CommandError
from questions.import_logic import import_questions_from_csv


class Command(BaseCommand):
    help = 'Import questions from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to the CSV file')

    def handle(self, *args, **options):
        filepath = options['file']
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                result = import_questions_from_csv(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {filepath}")
        except Exception as e:
            raise CommandError(f"Failed to read file: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\nImport complete:\n"
            f"  Inserted : {result['inserted']}\n"
            f"  Skipped  : {result['skipped']}\n"
            f"  Errors   : {result['errors']}\n"
        ))

        if result['error_details']:
            self.stdout.write(self.style.WARNING("Error details:"))
            for detail in result['error_details']:
                self.stdout.write(f"  {detail}")
