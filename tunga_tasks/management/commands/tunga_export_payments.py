import csv

from django.core.management.base import BaseCommand
from django.template.defaultfilters import floatformat

from tunga.settings import TUNGA_URL
from tunga_tasks.models import ParticipantPayment


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Update periodic update events and send notifications for upcoming update events.
        """
        # command to run: python manage.py tunga_export_payments

        participant_payments = ParticipantPayment.objects.filter(participant__task__paid=True)

        print('participant_payments', len(participant_payments))
        with open('developer_payments.csv', 'wb') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='"', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow([
                'Task', 'Fee', 'Developer', 'Dev BTC Address', 'BTC Sent', 'Task BTC Address', 'Invoice Date',
                'Paid By', 'URL', 'Developer Invoice', 'Client Invoice'
            ])

            for payment in participant_payments:
                row = [
                    payment.participant.task.summary, 'EUR {}'.format(floatformat(payment.participant.task.fee, -2)),
                    payment.participant.user.display_name, payment.destination,
                    'BTC {}'.format(floatformat(payment.btc_sent, -6)), payment.participant.task.btc_address,
                    payment.participant.task.taskinvoice_set.first().created_at.strftime("%d %b, %Y"),
                    payment.participant.task.user.display_name,
                    '{}/work/{}'.format(TUNGA_URL, payment.participant.task.id),
                    '{}/api/task/{}/download/invoice/?format=pdf&type=developer'.format(TUNGA_URL, payment.participant.task.id),
                    '{}/api/task/{}/download/invoice/?format=pdf&type=client'.format(TUNGA_URL, payment.participant.task.id)
                ]
                spamwriter.writerow(row)
