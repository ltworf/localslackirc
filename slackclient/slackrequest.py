# localslackirc
# Copyright (C) 2018 Salvo "LtWorf" Tomaselli
#
# localslackirc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# author Salvo "LtWorf" Tomaselli <tiposchi@tiscali.it>
#
# This file was part of python-slackclient
# (https://github.com/slackapi/python-slackclient)
# But has been copied and relicensed under GPL. The copyright applies only
# to the changes made since it was copied.

import json
from typing import Dict, Optional

import requests
import six


class SlackRequest(object):
    def __init__(self, proxies=None):
        self.proxies = proxies

    def do(self, token: str, request: str, post_data: Dict[str,str], timeout: Optional[float]):
        """
        Perform a POST request to the Slack Web API

        Args:
            token (str): your authentication token
            request (str): the method to call from the Slack API. For example: 'channels.list'
            timeout (float): stop waiting for a response after a given number of seconds
            post_data (dict): key/value arguments to pass for the request. For example:
                {'channel': 'CABC12345'}
            domain (str): if for some reason you want to send your request to something other
                than slack.com
        """
        domain = "slack.com"

        url = 'https://{0}/api/{1}'.format(domain, request)

        # Set user-agent and auth headers
        headers = {
            'user-agent': 'localslackirc',
            'Authorization': 'Bearer {}'.format(token)
        }

        # Pull file out so it isn't JSON encoded like normal fields.
        # Only do this for requests that are UPLOADING files; downloading files
        # use the 'file' argument to point to a File ID.

        # Move singular file objects into `files`
        upload_requests = ['files.upload']

        # Move file content into requests' `files` param
        files = None
        if request in upload_requests:
            files = {'file': post_data.pop('file')} if 'file' in post_data else None

        # Check for plural fields and convert them to comma-separated strings if needed
        for field in {'channels', 'users', 'types'} & set(post_data.keys()):
            if isinstance(post_data[field], list):
                post_data[field] = ",".join(post_data[field])

        # Convert any params which are list-like to JSON strings
        # Example: `attachments` is a dict, and needs to be passed as JSON
        for k, v in six.iteritems(post_data):
            if isinstance(v, (list, dict)):
                post_data[k] = json.dumps(v)

        # Submit the request
        return requests.post(
            url,
            headers=headers,
            data=post_data,
            files=files,
            timeout=timeout,
            proxies=self.proxies
        )
