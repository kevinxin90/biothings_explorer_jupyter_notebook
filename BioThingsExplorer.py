import matplotlib as mpl
import networkx as nx
import visJS2jupyter.visJS_module
from IPython.display import HTML, display
import tabulate

from api_handler import SmartAPIHandler
from jsonld_processor import jsonld2nquads, fetchvalue

    
class pathViewer:
    def __init__(self):
        self.graph_id = 5
        self.api_handler = SmartAPIHandler()
        # place holder for triples (input, endpoint, output)
        self.triples = []
        self.paths = []
        self.selected_path = None
        self.final_results = {}
        self.start_point = ''
        self.G = None
        self.edges = []
        self.nodes = []
        self.edge_relation_dict = {}
        self.node_to_color = {}
        self.filter = None
    
    def draw_graph(self, nodes, edges, node_to_color=None, edge_relation_dict={}, edge_font_size = 10, edge_font_align="bottom"):
        self.G = nx.Graph()
        self.G.add_nodes_from(nodes)
        self.G.add_edges_from(edges)
        nodes = self.G.nodes()
        if not edge_relation_dict:
            edge_relation_dict = dict(zip(edges, ['is_related_to']*len(edges)))
        cc = nx.clustering(self.G)
        degree = {}
        for _node in nodes:
            degree.update({_node: 1})
        bc = nx.betweenness_centrality(self.G)
        nx.set_node_attributes(self.G, 'clustering_coefficient', cc)
        nx.set_node_attributes(self.G, 'degree', degree)
        nx.set_node_attributes(self.G, 'betweenness_centrality', bc)
        pos = nx.circular_layout(self.G)
        # if user didn't specify the color of node, use the default one
        if not node_to_color:
            node_to_color = visJS2jupyter.visJS_module.return_node_to_color(self.G, field_to_map='betweenness_centrality', cmap=mpl.cm.spring_r, alpha=1,
                                                                            color_max_frac=.9, color_min_frac=.1)
        nodes_dict = [{"id": n, "color": node_to_color[n], "value": 2, "degree": 3, "x": pos[n][0]*1000, "y": pos[n][0]*1000} for n in nodes]
        node_map = dict(zip(nodes, range(len(nodes))))  # map to indices for source/target in edges
        edges_dict = [{"source": node_map[edges[i][0]], "target": node_map[edges[i][1]],
                      "color": "gray", "title": 'test', "id": edge_relation_dict[edges[i]]} for i in range(len(edges))]
        self.graph_id += 1
        return visJS2jupyter.visJS_module.visjs_network(nodes_dict, edges_dict, graph_id=self.graph_id, edge_arrow_to=True, edge_arrow_to_scale_factor=0.4, node_font_size=15, node_font_align='left', edge_font_align=edge_font_align, edge_font_size = edge_font_size)
    '''
    show all available ids in the package, together with URI, description, identifeir pattern 
    and data type, e.g. entity/object
    '''
    def available_ids(self):
        table = [['Preferred Name', 'URI', 'Description', 'Identifier pattern', 'Type']]
        for uri, info in self.api_handler.bioentity_info.items():
            table.append([info['preferred_name'], uri, info['description'], info['identifier_pattern'], info['type']])
        return display(HTML(tabulate.tabulate(table, tablefmt='html')))
    
    '''
    Call the function to show the how APIs, Endpoints & Input/outputs are connected together
    '''
    def show_api_road_map(self, display_graph=True):
        if display_graph and self.nodes and self.edges and self.node_to_color:
            return self.draw_graph(self.nodes, self.edges, self.node_to_color, self.edge_relation_dict)
        nodes = []
        edges = []
        edge_relation_dict = {}
        node_to_color = {}
        for _api, _info in self.api_handler.api_info.items():
            nodes.append(_api)
            node_to_color.update({_api: 'red'})
            for _endpoint in _info['endpoints']:
                nodes.append(_endpoint)
                node_to_color.update({_endpoint: 'blue'})
                _edge = (_api, _endpoint)
                edges.append(_edge)
                edge_relation_dict[_edge] = 'has_endpoint'
        for _endpoint, _info in self.api_handler.endpoint_info.items():
            input = _info['get']['parameters'][0]['x-valueType']
            output = _info['output']
            for _input in input:
                nodes.append(self.api_handler.bioentity_info[_input]['preferred_name'])
                node_to_color.update({self.api_handler.bioentity_info[_input]['preferred_name']: 'yellow'})
                _edge = (self.api_handler.bioentity_info[_input]['preferred_name'], _endpoint)
                edges.append(_edge)
                if _edge not in edge_relation_dict:
                    edge_relation_dict[_edge] = ''
                    self.edge_relation_dict[_edge] = ''
                for _output in output:
                    if {'input': self.api_handler.bioentity_info[_input]['preferred_name'], 'endpoint': _endpoint, 'output': self.api_handler.bioentity_info[_output]['preferred_name']} not in self.triples:
                        self.triples.append({'input': self.api_handler.bioentity_info[_input]['preferred_name'], 'endpoint': _endpoint, 'output': self.api_handler.bioentity_info[_output]['preferred_name']})
            for _output in output:
                nodes.append(self.api_handler.bioentity_info[_output]['preferred_name'])
                node_to_color.update({self.api_handler.bioentity_info[_output]['preferred_name']: 'yellow'})
                _edge = (_endpoint, self.api_handler.bioentity_info[_output]['preferred_name'])
                edges.append(_edge)
                if len(_info['relation'][_output]) == 1:
                    edge_relation_dict[_edge] = _info['relation'][_output][0].split(':')[1]
                    self.edge_relation_dict[_edge] = _info['relation'][_output][0].split(':')[1]
                else:
                    edge_relation_dict[_edge] = 'multi'
                    self.edge_relation_dict[_edge] = [_relation.split(':')[1] for _relation in _info['relation'][_output]]
        self.nodes = nodes
        self.edges = edges
        self.node_to_color = node_to_color
        if display_graph:
            return self.draw_graph(nodes, edges, node_to_color, edge_relation_dict, edge_font_size=5)
    
    def explore_api(self, api_name):
        endpoint_nodes = []
        nodes = []
        edges = []
        node_to_color = {api_name: 'red'}
        edge_relation_dict = {}
        for _edge in self.edges:
            if _edge[0] == api_name:
                endpoint_nodes.append(_edge[1])
                nodes.append(_edge[1])
                node_to_color[_edge[1]] = 'blue'
                edges.append(_edge)
        for _node in endpoint_nodes:
            for _edge in self.edges:
                if _edge[0] == _node:
                    nodes.append(_edge[1])
                    edges.append(_edge)
                    node_to_color[_edge[1]] = 'yellow'
                elif _edge[1] == _node:
                    nodes.append(_edge[0])
                    edges.append(_edge)
                    if _edge[0] != api_name:
                        node_to_color[_edge[0]] = 'yellow'
        for _edge in edges:
            if _edge[0] == api_name:
                edge_relation_dict[_edge] = 'has_endpoint'
            else:
                edge_relation_dict[_edge] = self.edge_relation_dict[_edge]
        return self.draw_graph(nodes, edges, node_to_color, edge_relation_dict)



    def create_node_edge_from_triple(self, _triple):
        nodes = [_triple['input'], _triple['output'], _triple['endpoint']]
        edges = [(_triple['input'], _triple['endpoint']), (_triple['endpoint'], _triple['output'])]
        return (nodes, edges)

    def create_node_edge_from_path(self, paths, filter):
        nodes = []
        edges = []
        edge_relation_dict = {}
        for _path in paths:
            nodes += _path
            i = 0
            while i < len(_path) -1:
                _edge = (_path[i], _path[i+1])
                edges.append(_edge)
                if type(self.edge_relation_dict[_edge]) != list:
                    edge_relation_dict[_edge] = self.edge_relation_dict[_edge]
                else:
                    if filter and filter in self.edge_relation_dict[_edge]:
                        edge_relation_dict[_edge] = filter
                    else:
                        edge_relation_dict[_edge] = 'multi'
                        print('The path connecting "{}" and "{}" contains multiple edges: {}\n'.format(_edge[0], _edge[1], ','.join(self.edge_relation_dict[_edge])))
                _edge = (_path[i+1], _path[i+2])
                edges.append(_edge)
                if type(self.edge_relation_dict[_edge]) != list:
                    edge_relation_dict[_edge] = self.edge_relation_dict[_edge]
                else:
                    if filter and filter in self.edge_relation_dict[_edge]:
                        edge_relation_dict[_edge] = filter
                    else:
                        edge_relation_dict[_edge] = 'multi'
                        print('The path connecting "{}" and "{}" contains {} different edges: {}'.format(_edge[0], _edge[1], len(self.edge_relation_dict[_edge]), ','.join(self.edge_relation_dict[_edge])))
                i += 2
        return (nodes, edges, edge_relation_dict)

    def find_children(self, node):
        for _edge in self.edges:
            if _edge[0] == node:
                yield _edge[1]

    def find_path(self, start, end, display_graph=True, max_no_api_used=4, intermediate_nodes=[], excluded_nodes=[], filter=None):
        self.filter = filter
        cutoff = max_no_api_used * 2 + 1
        if cutoff < 1:
            print('please specify max_no_api_used with a number >= 1')
            return
        if start not in self.nodes or end not in self.nodes:
            print('the start and end position is not in the api_map')
            return
        visited = [start]
        stack = [self.find_children(start)]
        paths = []
        final_results = []
        while stack:
            children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop()
                visited.pop()
            elif len(visited) < cutoff:
                if child == end:
                    new_path = visited + [end]
                    if new_path not in paths:
                        paths.append(visited + [end])
                elif child not in visited:
                    visited.append(child)
                    stack.append(self.find_children(child))
            else: #len(visited) == cutoff:
                if child == end or end in children:
                    new_path = visited + [end]
                    if new_path not in paths:
                        paths.append(visited + [end])
                stack.pop()
                visited.pop()
        if intermediate_nodes:
            if type(intermediate_nodes)!=list:
                intermediate_node = [intermediate_nodes]
            for _node in intermediate_nodes:
                if _node not in self.nodes:
                    print('the intermediate node is not in the map')
                    return
            for _path in paths:
                if set(intermediate_nodes) < set(_path):
                    print('yes path: {}'.format(path))
                    if excluded_nodes:
                        if (set(_path) - set(excluded_nodes)) == set(_path):
                            final_results.append(_path)
                    else:
                        final_results.append(_path)
                else:
                    return
        else:
            if excluded_nodes:
                for _path in paths:
                    if (set(_path) - set(excluded_nodes)) == set(_path):
                        final_results.append(_path)
            else:
                final_results = paths
        if final_results:
            self.paths = final_results
            print('The following lists all paths connecting from "{}" to "{}":\n'.format(start, end))
            for i, _path in enumerate(final_results):
                print('[Path {}]: {}\n'.format(i, ' -> '.join(_path)))

            (nodes, edges, edge_relation_dict) = self.create_node_edge_from_path(final_results, filter=filter)

            return self.draw_graph(nodes, edges, None, edge_relation_dict, edge_font_size=15)

    def path_handler(self, path, value):
        result = []
        # convert id name to uri
        for k, v in self.api_handler.bioentity_info.items():
            if v['preferred_name'] == path['input']:
                _input = k
            elif v['preferred_name'] == path['output']:
                _output = k
        if type(value) != list:
            value = [value]
        # make api call with input and endpoint name
        for _value in value:
            (outputs, output_type) = self.api_handler.call_api(_input, _value, path['endpoint'], _output)
            for output in outputs:
                if output_type == 'Entity':
                    result.append((_value, output[0], output_type, output[1]))
                else:
                    result.append((_value, output, output_type))
        return result

    def path_conversion(self, path):
        i = 0
        new_path = []
        while i < len(path) -2:
            new_path.append({'input': path[i], 'endpoint': path[i+1], 'output': path[i+2]})
            i += 2
        return new_path

    def explore_all_paths(self, value):
        result = {}
        nodes = []
        edges = []
        node_to_color = {}
        color = ['yellow', 'blue', 'green', 'orange', 'pink', 'purple', 'brown']
        edge_relation_dict = {}
        for i, _path in enumerate(self.paths):
            _path = self.path_conversion(_path)
            (_nodes, _edges, _edge_relation_dict, _result) = self.find_output(_path, value, display_graph=False)
            for _node in _nodes:
                if _node not in nodes:
                    node_to_color.update({_node: color[i]})
                    nodes.append(_node)
                else:
                    node_to_color.update({_node: 'red'})
            edges += _edges
            result['path' + str(i)] = _result
            edge_relation_dict = {**_edge_relation_dict, **edge_relation_dict}
        self.final_results = result
        return self.draw_graph(nodes, edges, node_to_color, edge_relation_dict)


    def find_output(self, path, value, display_graph=True):
        result = []
        nodes = []
        edges = []
        object_id = 0
        edge_relation_dict = {}
        self.selected_path = path
        self.start_point = value
        self.final_results = {}
        if type(value) != list:
            value = [value]
        for _value in value:
            if len(path) == 1:
                result = self.path_handler(path[0], _value)
                if result[0][2] == 'Entity':
                    self.final_results.update({_value: [(path[0]['output'] + ':' + _result[1]) for _result in result]})
                else:
                    self.final_results.update({_value: [_result[1] for _result in result]})
                for _result in result:
                    if _result[2] == 'Entity':
                        nodes += [path[0]['input'] + ':' + _result[0], path[0]['output'] + ':' + _result[1]]
                        edges += [(path[0]['input'] + ':' + _result[0], path[0]['output'] + ':' + _result[1])]
                        edge_relation_dict[(path[0]['input'] + ':' + _result[0], path[0]['output'] + ':' + _result[1])] = _result[3]
                    else:
                        object_node = str(len(result)) + ' ' + path[-1]['output'] + 's'
                        if object_node in nodes:
                            object_node = str(len(result)) + ' ' + path[-1]['output'] + 's (' + str(object_id) + ')'
                            object_id += 1
                        nodes += [path[0]['input'] + ':' + _result[0], object_node]
                        edges += [(path[0]['input'] + ':' + _result[0], object_node)]
                        break
            else:
                _input = _value
                for i, _path in enumerate(path):
                    response = self.path_handler(_path, _input)
                    result += response
                    _input = [_response[1] for _response in response]
                    if i == len(path) -1:
                        if response[0][2] == 'Entity':
                            self.final_results.update({_value: [_path['output'] + ':' + _inp for _inp in _input]})
                        else:
                            self.final_results.update({_value: _input})
                    for _result in response:
                        if _result[2] == 'Entity':
                            nodes += [_path['input'] + ':' + _result[0], _path['output'] + ':' + _result[1]]
                            edges += [(_path['input'] + ':' + _result[0], _path['output'] + ':' + _result[1])]
                            edge_relation_dict[(_path['input'] + ':' + _result[0], _path['output'] + ':' + _result[1])] = _result[3]
                        else:
                            object_node = str(len(self.final_results[_value])) + ' ' + path[-1]['output'] + 's'
                            if object_node in nodes:
                                object_node = str(len(self.final_results[_value])) + ' ' + path[-1]['output'] + 's (' + str(object_id) + ')'
                                object_id += 1
                            nodes += [_path['input'] + ':' + _result[0], object_node]
                            edges += [(_path['input'] + ':' + _result[0], object_node)]
                            edge_relation_dict[(_path['input'] + ':' + _result[0], object_node)] = 'isRelatedTo'
                            break
        if display_graph:
            return self.draw_graph(nodes, edges, None, edge_relation_dict)
        else:
            return (nodes, edges, edge_relation_dict, self.final_results)

    def result_summary(self):
        print("Your exploration starts from {}: {}. \n It goes through {} API Endpoints. \n The final output comes from API Endpoint {}. \n You can access the final output by calling the 'final_results' object in pathViewer Class.\n".format(self.selected_path[0]['input'], self.start_point, len(self.selected_path), self.selected_path[-1]['endpoint']))

