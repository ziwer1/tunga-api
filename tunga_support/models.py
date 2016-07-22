from __future__ import unicode_literals

from django.db import models

from tunga import settings

VISIBILITY_ALL = 'all'
VISIBILITY_DEVELOPERS = 'developers'
VISIBILITY_PROJECT_OWNERS = 'project-owners'

VISIBILITY_CHOICES = (
    (VISIBILITY_ALL, 'Everyone'),
    (VISIBILITY_DEVELOPERS, 'Developers'),
    (VISIBILITY_PROJECT_OWNERS, 'Project Owners')
)


class SupportSection(models.Model):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=20, unique=True, help_text='url path for this section')
    order = models.PositiveSmallIntegerField(default=0, help_text='0 is the highest order')
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_ALL,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in VISIBILITY_CHOICES])
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='support_sections_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.title

    class Meta:
        verbose_name = 'section'
        verbose_name_plural = 'sections'
        ordering = ['order', 'title', '-created_at']


class SupportPage(models.Model):
    section = models.ForeignKey(SupportSection, related_name='pages', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=20, help_text="url path for this page (should not include the section slug)")
    content = models.TextField()
    order = models.PositiveSmallIntegerField(default=0, help_text='0 is the highest order')
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_ALL,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in VISIBILITY_CHOICES])
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='support_pages_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.title

    class Meta:
        verbose_name = 'page'
        verbose_name_plural = 'pages'
        ordering = ['order', 'title', '-created_at']
        unique_together = ('section', 'slug')
