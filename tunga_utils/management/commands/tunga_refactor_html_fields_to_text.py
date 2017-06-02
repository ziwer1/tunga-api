from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q

from tunga_comments.models import Comment
from tunga_messages.models import Message
from tunga_profiles.models import UserProfile, Work, Education
from tunga_tasks.models import Task, Application, ProgressEvent, ProgressReport
from tunga_utils.helpers import convert_to_text


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Fix payment rates based on task status
        """
        # command to run: python manage.py tunga_refactor_html_fields_to_text

        # Fix profiles
        profiles = UserProfile.objects.filter(Q(bio__isnull=False) & ~Q(bio=''))
        for item in profiles:
            item.bio = convert_to_text(item.bio)
            item.save()
        print('profiles', len(profiles))

        # Fix messages
        messages = Message.objects.filter(Q(body__isnull=False) & ~Q(body=''))
        for item in messages:
            item.body = convert_to_text(item.body)
            item.save()
        print('messages', len(messages))

        # Fix comments
        comments = Comment.objects.filter(Q(body__isnull=False) & ~Q(body=''))
        for item in comments:
            item.body = convert_to_text(item.body)
            item.save()
        print('comments', len(comments))

        # Fix tasks
        tasks = Task.objects.all()
        for item in tasks:
            item.description = convert_to_text(item.description)
            item.remarks = convert_to_text(item.remarks)
            item.stack_description = convert_to_text(item.stack_description)
            item.deliverables = convert_to_text(item.deliverables)
            item.save()
        print('tasks', len(tasks))

        # Fix applications
        applications = Application.objects.all()
        for item in applications:
            item.pitch = convert_to_text(item.pitch)
            item.remarks = convert_to_text(item.remarks)
            item.save()
        print('applications', len(applications))

        # Fix progress events
        progress_events = ProgressEvent.objects.all()
        for item in progress_events:
            item.description = convert_to_text(item.description)
            item.save()
        print('progress events', len(progress_events))

        # Fix progress events
        progress_reports = ProgressReport.objects.all()
        for item in progress_reports:
            item.accomplished = convert_to_text(item.accomplished)
            item.todo = convert_to_text(item.todo)
            item.obstacles = convert_to_text(item.obstacles)
            item.remarks = convert_to_text(item.remarks)
            item.save()
        print('progress reports', len(progress_reports))

        # Fix work
        work = Work.objects.all()
        for item in work:
            item.details = convert_to_text(item.details)
            item.save()
        print('work', len(work))

        # Fix education
        education = Education.objects.all()
        for item in education:
            item.details = convert_to_text(item.details)
            item.save()
        print('education', len(education))
