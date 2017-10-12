import requests
import yaml
import pandas as pd
import pprint
from jsonld_processor import jsonld2nquads, fetchvalue

class SmartAPIHandler:
    def __init__(self):
        # description info about endpoint, bioentity and api
        self.endpoint_info = {}
        self.bioentity_info = {}
        self.api_info = {}
        self.parse_id_mapping()
        self.parse_openapi()
    '''
    This function parse the openapi yml file, and organize info into endpoints and apis
    '''
    def parse_openapi(self):
        api_list_url = 'https://raw.githubusercontent.com/NCATS-Tangerine/translator-api-registry/master/API_LIST.yml'
        api_list = yaml.load(requests.get(api_list_url).content)['APIs']
        # path to fetch openapi yml file for each api
        metadata_url_prefix = "https://raw.githubusercontent.com/NCATS-Tangerine/translator-api-registry/master/"
        for _api in api_list:
            openapi_url = metadata_url_prefix + _api['metadata']
            # check if the openapi file for the api exists first
            if requests.get(openapi_url).status_code == 200:
                # retrieve openapi file
                openapi_file = requests.get(openapi_url).content
                data = yaml.load(openapi_file)
                self.api_info[data['info']['title']] = {'info': data['info'], 'servers': data['servers'], 'endpoints': []}
                for _name, _info in data['paths'].items():
                    self.endpoint_info[data['servers'][0]['url'] + _name] = _info
                    _output = [_item['valueType'] for _item in _info['get']['responses']['200']['x-responseValueType']]
                    self.endpoint_info[data['servers'][0]['url'] + _name].update({'output': _output})

                    self.api_info[data['info']['title']]['endpoints'].append(data['servers'][0]['url'] + _name)
            else:
                print("invalid url for openapi: {}".format(openapi_url))

    '''
    construct requests params/data, based on input type and value
    only handle 'in' value which is body or query
    '''
    def api_call_constructor(self, uri, value, endpoint_name):
        results = {}
        method = type(value) == list and 'post' or 'get'
        for _para in self.endpoint_info[endpoint_name][method]['parameters']:
            # handle cases where input value is part of the url
            if _para['in'] == 'path':
                data = requests.get(endpoint_name.replace(_para['name'], value))
                return data
            else:
                # check whether the parameter is required
                if _para['required']:
                    # if the para has a request template, then put value into the placeholder {{input}}
                    if 'x-requestTemplate' in _para:
                        for _template in _para['x-requestTemplate']:
                            if _template['valueType'] == 'default':
                                results[_para['name']] = _template['template'].replace('{{input}}', value)
                            elif uri == _template['valueType']:
                                results[_para['name']] = _template['template'].replace('{{input}}', value)
                    else:
                        results[_para['name']] = value
        pprint.pprint(results)
        if type(value) != list:
            data = requests.get(endpoint_name, params=results)
        else:
            data = requests.post(endpoint_name, data=results)
        return data
  
    '''
    parse the uri_id mapping file, return a dict containing id mapping info indexed by uri
    '''
    def parse_id_mapping(self):
        file_url = 'https://raw.githubusercontent.com/NCATS-Tangerine/translator-api-registry/master/ID_MAPPING.csv'
        data = pd.read_csv(file_url, encoding = "ISO-8859-1")
        for index, row in data.iterrows():
            self.bioentity_info[row['URI']] = {'registry_identifier': row[2], 'alternative_names': row[3], 'description': row[4], 'identifier_pattern': row[5], 'preferred_name': row[1], 'type': row[6]}
        return self.bioentity_info

    '''
    fetch endpoint jsonld contextinformation
    '''
    def fetch_context(self, endpoint_name):
        file_url = self.endpoint_info[endpoint_name]['get']['responses']['200']['x-JSONLDContext']
        return requests.get(file_url).json()

    '''
    input: user provide input/output
    output: return endpoint(s) which could take the input and return the output
    '''
    def api_endpoint_locator(self, input, output):
        endpoint_list = []
        for _endpoint, _info in self.endpoint_info.items():
            if input in _info['get']['parameters'][0]['x-valueType'] and output in _info['output']:
                endpoint_list.append(_endpoint)
        return endpoint_list

    '''
    make api calls based on input, endpoint
    '''
    def call_api(self, input, value, endpoint, output):
        json_doc = self.api_call_constructor(input, value, endpoint).json()
        if endpoint.startswith('http://myvariant.info/'):
            if "_id" in json_doc:
                json_doc["_id"] = json_doc["_id"].replace(':', '-')
            elif "hits" in json_doc:
                for _doc in json_doc["hits"]:
                    if "_id" in _doc:
                        _doc['_id'] = _doc['_id'].replace(":", "-")
        output_type = self.bioentity_info[output]['type']
        if output_type == 'Entity':
            jsonld_context = self.fetch_context(endpoint)
            json_doc.update(jsonld_context)
            # parse output nquads
            nquads = jsonld2nquads(json_doc)
            outputs = list(set(fetchvalue(nquads, output)))
            return (outputs,output_type)
        else:
            response = self.endpoint_info[endpoint]['get']['responses']['200']['x-responseValueType']
            for _response in response:
                if _response['valueType'] == output:
                    output_path = _response['path']
            outputs_command = 'json_doc'
            for _item in output_path.split('.'):
                outputs_command += ('["' + _item + '"]')
            outputs = eval(outputs_command)
            return (outputs, output_type)
