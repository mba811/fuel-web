# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from nailgun.api.v1.validators.base import BasicValidator
from nailgun import consts
from nailgun.db import db
from nailgun.errors import errors
from nailgun import objects

from nailgun.api.v1.validators.json_schema import node_group


class NodeGroupValidator(BasicValidator):

    single_schema = node_group.single_schema

    @classmethod
    def _validate_unique_name(cls, data, *filters):
        """Validate node group name to be unique.

        Validate whether node group name is unique for specific
        environment. Prevent to have duplicated node group names for
        the same environment.

        :param data: data which contains node group name and cluster_id.
        :param filters: additional filters for the query which is
                        used in the method for validation.
        :type data: dict
        :type filters: list
        :returns: None
        """
        nodegroup_query = objects.NodeGroupCollection.filter_by(
            None, name=data['name'], cluster_id=data['cluster_id'])
        if filters:
            nodegroup_query = nodegroup_query.filter(*filters)
        nodegroup_exists = db.query(nodegroup_query.exists()).scalar()
        if nodegroup_exists:
            raise errors.NotAllowed(
                "Node group '{0}' already exists "
                "in environment {1}.".format(
                    data['name'], data['cluster_id']))

    @classmethod
    def validate(cls, data):
        data = cls.validate_json(data)
        cluster = objects.Cluster.get_by_uid(
            data['cluster_id'], fail_if_not_found=True)

        cls._validate_unique_name(data)

        if cluster.net_provider == consts.CLUSTER_NET_PROVIDERS.nova_network:
            raise errors.NotAllowed(
                "Node groups can only be created when using Neutron."
            )

        return data

    @classmethod
    def validate_delete(cls, data, instance, force=False):
        if (instance.nodes or instance.networks) and not force:
            raise errors.CannotDelete(
                "You cannot delete a node group that contains "
                "nodes or networks"
            )

    @classmethod
    def validate_update(cls, data, instance):
        data = cls.validate_json(data)
        cls._validate_unique_name(
            data, objects.NodeGroup.model.id != instance.id)
        return data
