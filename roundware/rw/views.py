#***********************************************************************************#

# ROUNDWARE
# a contributory, location-aware media platform

# Copyright (C) 2008-2014 Halsey Solutions, LLC
# with contributions from:
# Mike MacHenry, Ben McAllister, Jule Slootbeek and Halsey Burgund (halseyburgund.com)
# http://roundware.org | contact@roundware.org

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see
# <http://www.gnu.org/licenses/lgpl.html>.

#***********************************************************************************#


from chartit.chartdata import PivotDataPool
from chartit.charts import PivotChart
from django.db.models.aggregates import Count, Sum
from django.http import HttpResponse
import time
import string
import os
import logging
import json
import traceback

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.template.context import RequestContext
from django.forms.models import save_instance
from django.views.generic.base import TemplateView
from django.utils.safestring import mark_safe

from guardian.core import ObjectPermissionChecker
from guardian.mixins import PermissionRequiredMixin
from braces.views import (LoginRequiredMixin, FormValidMessageMixin,
                          AjaxResponseMixin)
from extra_views import InlineFormSet, CreateWithInlinesView, UpdateWithInlinesView
from extra_views.multi import MultiFormView, FormProvider

from roundware.rw.chart_functions import assets_created_per_day
from roundware.rw.chart_functions import sessions_created_per_day
from roundware.rw.chart_functions import assets_by_question
from roundware.rw.chart_functions import assets_by_section
from roundware.rw.models import Tag, MasterUI, UIMapping, Project
from roundware.rw.forms import (TagCreateForm, BatchTagFormset,
                                # MasterUIForSetupTagUICreateForm,
                                MasterUIForSetupTagUIEditForm,
                                MasterUIForSetupTagUISelectForm)
from roundware.rw.widgets import SetupTagUISortedCheckboxSelectMultiple
from roundwared import settings
from roundwared import roundexception
from roundwared import server
logger = logging.getLogger(__name__)


def main(request):
    return HttpResponse(json.dumps(catch_errors(request), sort_keys=True, indent=4, ensure_ascii=False), content_type='application/json')


def catch_errors(request):
    try:
        config_file = "rw"
        if 'config' in request.GET:
            config_file = request.GET['config']
        settings.initialize_config(
            os.path.join('/etc/roundware/', config_file))

        if 'operation' in request.GET:
            function = operation_to_function(request.GET['operation'])
        elif 'operation' in request.POST:
            function = operation_to_function(request.POST['operation'])
        return function(request)
    except roundexception.RoundException as e:
        logger.error(str(e) + traceback.format_exc())
        return {"error_message": str(e)}
    except:
        logger.error(
            "An uncaught exception was raised. See traceback for details." +
            traceback.format_exc())
        return {
            "error_message": "An uncaught exception was raised. See traceback for details.",
            "traceback": traceback.format_exc(),
        }


def operation_to_function(operation):
    if not operation:
        raise roundexception.RoundException("Operation is required")
    operations = {
        "request_stream": server.request_stream,
        "heartbeat": server.heartbeat,
        "current_version": server.current_version,
        "log_event": server.log_event,
        "create_envelope": server.create_envelope,
        "add_asset_to_envelope": server.add_asset_to_envelope,
        "get_config": server.get_config,
        "get_tags": server.get_tags_for_project,
        "modify_stream": server.modify_stream,
        "get_current_streaming_asset": server.get_current_streaming_asset,
        "get_asset_info": server.get_asset_info,
        "get_available_assets": server.get_available_assets,
        "play_asset_in_stream": server.play_asset_in_stream,
        "vote_asset": server.vote_asset,
        "skip_ahead": server.skip_ahead,
        "get_events": server.get_events,
    }
    key = string.lower(operation)
    if key in operations:
        return operations[key]
    else:
        raise roundexception.RoundException("Invalid operation, " + operation)


from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required


@login_required
def chart_views(request):

    asset_created_per_day_chart = assets_created_per_day()
# return render_to_response("chart_template.html", {'assetchart':
# asset_created_per_day_chart})

    session_created_per_day_chart = sessions_created_per_day()
    assets_by_question_chart = assets_by_question()
    assets_by_section_chart = assets_by_section()
# return render_to_response("chart_template.html", {'sessionchart':
# session_created_per_day_chart, 'assetchart':
# asset_created_per_day_chart})
    return render_to_response("chart_template.html", {'charts': [session_created_per_day_chart, asset_created_per_day_chart, assets_by_question_chart, assets_by_section_chart]})


class MultiCreateTagsView(LoginRequiredMixin, FormValidMessageMixin, MultiFormView):
    success_url = '/admin/rw/tag'
    template_name = 'rw/tags_add_to_category_form.html'
    form_valid_message = 'Tags created!'
    forms = {'category': MultiFormView.modelform(Tag, TagCreateForm,
                                                 **{'fields': ('tag_category',),
                                                    'exclude': ('value', 'description', 'data',
                                                                'loc_msg')}
                                                 ),
             'tag_formset': MultiFormView.modelformset(Tag,
                                                       **{'extra': 2, 'form': TagCreateForm,
                                                          'exclude': ['tag_category'],
                                                          'fields': ['value', 'description', 'data', 'loc_msg'],
                                                           'formset': BatchTagFormset}
                                                       )
             }

    def get_category_instance(self):
        return Tag()

    def get_tag_formset_queryset(self):
        return Tag.objects.none()

    def valid_all(self, valid_forms):
        """ handle case all forms valid
        """
        category = valid_forms['category']
        formset = valid_forms['tag_formset']
        for form in formset.forms:
            tag = form.save(commit=False)  # doesn't save m2m yet
            tag.tag_category = category.cleaned_data['tag_category']
            tag.save()
            form.save_m2m()

    def invalid_all(self, invalid_forms):
        """ handle case all forms invalid
        """
        self.forms_invalid(invalid_forms)


class UIMappingsInline(InlineFormSet):
    model = UIMapping
    fk_name = 'master_ui'


class SetupTagUIMixin(LoginRequiredMixin, PermissionRequiredMixin):

    """ make sure User can modify this MasterUI based on Project,
        and is logged in.
    """
    permission_required = 'rw.access_project'
    return_403 = True

    def get_object(self):
        """ return Project for this MasterUI  as the object to check against
        """
        try:
            return get_object_or_404(Project, masterui=self.kwargs['pk'])
        except KeyError:
            return None


class MasterUIMappingsOrganizationView(SetupTagUIMixin, AjaxResponseMixin,
                                       MultiFormView):
    success_url = '.'
    template_name = 'setup_tag_ui_form.html'
    forms = {
        'master_ui_select': FormProvider(
            MasterUIForSetupTagUISelectForm,
            context_suffix='form',
            init_args={'user': 'get_%s_user'}),

        'master_ui_edit': MultiFormView.modelform(MasterUI,
                                                  MasterUIForSetupTagUIEditForm),

    }

    def get_master_ui_select_user(self):
        return self.request.user

    def get_master_ui_edit_instance(self):
        """ for calling with a primary key in the url. This is called magically
            by MultiFormView to get the instance for master_ui_edit form
        """
        if self.kwargs.get('pk'):
            return MasterUI.objects.filter(pk=self.kwargs['pk'])[0]
        elif self.request.POST.get('master_ui_edit-id', None):
            return MasterUI.objects.filter(
                pk=self.request.POST['master_ui_edit-id'])[0]
        else:
            return MasterUI()

    def post(self, request, *args, **kwargs):
        """ create or update MasterUI instance
        """
        return super(MasterUIMappingsOrganizationView, self).post(request, *args, **kwargs)

    def post_ajax(self, request, *args, **kwargs):
        """ handle post made from selecting MasterUI in 'master_ui_select'
            form. AJAX posts will only result from modelchoicefield select
            for MasterUI changing.
        """
        edit_form_template = 'rw/setup_tags_ui_edit_form.html'
        response_dic = {}

        # if modelchoicefield not empty
        if request.POST.get("master_ui_select-masterui"):
            id_to_update = request.POST["master_ui_select-masterui"]
            mui = MasterUI.objects.get(pk=id_to_update)
            edit_form = MasterUIForSetupTagUIEditForm(instance=mui)
            response_dic['mui_update_id'] = mui.id

        else:
            edit_form = MasterUIForSetupTagUIEditForm()

        response_dic['master_ui_edit_form'] = edit_form

        return HttpResponse(render_to_string(edit_form_template,
                                             response_dic,
                                             RequestContext(request)))

    def update_ui_mappings(self, uimaps, formtags, defaults, indexes, mui):
        uimaptags = []

        default_tags = [df.startswith('t') and Tag.objects.filter(pk=df.replace('t', ''))[0] or
                        UIMapping.objects.filter(pk=df)[0].tag for df in defaults]
        for uimap in uimaps:
            uimaptags.append(uimap.tag)
            if uimap.tag not in formtags:
                uimap.delete()
        for tag in formtags:
            try:
                index = indexes.index(str(tag.pk)) + 1
            except ValueError:
                index = 1
            is_default = tag in default_tags
            if tag not in uimaptags:
                uimap = UIMapping(tag=tag, master_ui=mui, active=True,
                                  index=index, default=is_default)
                uimap.save()
            else:
                uimap = [uim for uim in uimaps if uim.tag == tag][0]
                uimap.index = index
                uimap.default = is_default
                uimap.save()

    def valid_all(self, valid_forms):
        """ handle case all forms valid
        """
        select = valid_forms['master_ui_select']  # don't save anything
        select  # pyflakes
        form = valid_forms['master_ui_edit']
        mui_id = form.cleaned_data.get('id')
        formtags = form.cleaned_data['ui_mappings_tags']

        defaults = form.data['master_ui_edit-ui_mappings_tag_order'].split(',')
        if form.cleaned_data['ui_mappings_tags_indexes']:
            indexes = form.cleaned_data['ui_mappings_tags_indexes'].split(',')
            indexes = [el.startswith('t') and el.replace('t', '') or
                       UIMapping.objects.select_related('tag').filter(
                       pk=el)[0].tag.pk for el in indexes]
        else:
            indexes = []
        if mui_id:
            mui = MasterUI.objects.filter(pk=mui_id)[0]
            uimaps = UIMapping.objects.select_related(
                'tag').filter(master_ui=mui)
            # instance isn't constructed yet with data from form so we can't
            # use form.save() but have to do the following with construct=True
            save_instance(form, mui, form._meta.fields, 'form changed', True,
                          form._meta.exclude, True)
            self.update_ui_mappings(uimaps, formtags, defaults, indexes, mui)

        else:
            mui = form.save()
            self.update_ui_mappings([], formtags, defaults, indexes, mui)

    def invalid_all(self, invalid_forms):
        """ handle case all forms invalid
        """
        self.forms_invalid(invalid_forms)


class UpdateTagUIOrder(TemplateView):

    """ display the widget for the master_ui_edit_tag_order field as updated
        based on the value of the master_ui_edit_tags field on
        MasterUIMappingsOrganizationView edit form.
    """

    def __init__(self, **kwargs):
        self.widget = SetupTagUISortedCheckboxSelectMultiple()

    def choice_iterator(self):
        for uimap in self.queryset:
            yield (uimap.pk, uimap.tag.__unicode__())

    def post(self, request, *args, **kwargs):
        """ add or remove checkbox items to the order field based on contents
            of the master_ui_edit_tags field.  UIMappings may not exist
            corresponding to the chosen tag.  UIMappings will never exist for
            a newly created MasterUI.
        """

        tag_vals = [Tag.objects.filter(pk=t)[0] for t in request.POST.getlist(
            'tags[]')]
        mui = request.POST.getlist('mui')[0]

        if mui:
            self.queryset = UIMapping.objects.select_related('tag'
                                                             ).filter(master_ui__pk=mui, tag__in=tag_vals).order_by('index')
            filtered = self.queryset.filter(default=True)
        else:
            self.queryset = UIMapping.objects.none()
            filtered = self.queryset

        # if tag id in request is not present in queryset, then we need to
        # create a line in the widget for a new empty uimapping.  Store the
        # tag id in a hidden field on the widget
        tags_seen = [map.tag for map in self.queryset]
        tags_unseen = [t for t in tag_vals if t not in tags_seen]

        html = self.widget.render('master_ui_edit-ui_mappings_tag_order',
                                  value=[uimap.pk for uimap in filtered],
                                  attrs={
                                      u'id': u'id_master_ui_edit-ui_mappings_tag_order'},
                                  choices=self.choice_iterator(),
                                  new_maps=tags_unseen,)
        return HttpResponse(mark_safe(html))


@login_required
def asset_map(request):
    return render_to_response("asset-map.html")
