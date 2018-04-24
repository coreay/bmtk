from bmtk.simulator.core.io_tools import io
from bmtk.simulator.core.config import ConfigDict
from bmtk.utils import sonata
from bmtk.simulator.core.node_sets import NodeSet, NodeSetAll
#from bmtk.simulator.core.network_adaptors.sonata_nodes import SonataNodes
#from bmtk.simulator.core.network_adaptors.sonata_edges import SonataEdges

from bmtk.simulator.core import sonata_reader




class SimNetwork(object):
    def __init__(self):
        self._components = {}
        self._io = io

        self._node_adaptors = {}
        self._edge_adaptors = {}
        self._register_adaptors()

        self._node_populations = {}
        self._node_sets = {}

        self._edge_populations = []


    @property
    def io(self):
        return self._io

    @property
    def node_populations(self):
        return self._node_populations.values()

    def _register_adaptors(self):
        #self._node_adaptors['sonata'] = SonataNodes
        #self._edge_adaptors['sonata'] = SonataEdges
        pass

    def get_node_adaptor(self, name):
        return self._node_adaptors[name]

    def get_edge_adaptor(self, name):
        return self._edge_adaptors[name]

    def add_component(self, name, path):
        self._components[name] = path

    def get_component(self, name):
        if name not in self._components:
            self.io.log_exception('No network component set with name {}'.format(name))
        else:
            return self._components[name]

    def get_node_population(self, name):
        return self._node_populations[name]

    def get_node_set(self, node_set):
        if node_set in self._node_sets.keys():
            return self._node_sets[node_set]

        elif isinstance(node_set, (dict, list)):
            return NodeSet(node_set, self)

        else:
            self.io.log_exception('Unable to load or find node_set "{}"'.format(node_set))

    def add_nodes(self, node_population):
        pop_name = node_population.name
        if pop_name in self._node_populations:
            # Make sure their aren't any collisions
            self.io.log_exception('There are multiple node populations with name {}.'.format(pop_name))

        node_population.initialize(self)
        self._node_populations[pop_name] = node_population
        if node_population.mixed_nodes:
            # We'll allow a population to have virtual and non-virtual nodes but it is not ideal
            self.io.log_warning(('Node population {} contains both virtual and non-virtual nodes which can cause ' +
                                 'memory and build-time inefficency. Consider separating virtual nodes into their ' +
                                 'own population').format(pop_name))

        # Used in inputs/reports when needed to get all gids belonging to a node population
        self._node_sets[pop_name] = NodeSet({'population': pop_name}, self)

    @property
    def recurrent_edges(self):
        return [ep for ep in self._edge_populations if ep.recurrent_connections]

    def add_edges(self, edge_population):
        edge_population.initialize(self)
        pop_name = edge_population.name

        # Check that source_population exists
        src_pop_name = edge_population.source_nodes
        if src_pop_name not in self._node_populations:
            self.io.log_exception('Source node population {} not found. Please update {} edges'.format(src_pop_name,
                                                                                                       pop_name))

        # Check that the target population exists and contains non-virtual nodes (we cannot synapse onto virt nodes)
        trg_pop_name = edge_population.target_nodes
        if trg_pop_name not in self._node_populations or self._node_populations[trg_pop_name].virtual_nodes_only:
            self.io.log_exception(('Node population {} does not exists (or consists of only virtual nodes). ' +
                                   '{} edges cannot create connections.').format(trg_pop_name, pop_name))

        edge_population.set_connection_type(src_pop=self._node_populations[src_pop_name],
                                            trg_pop = self._node_populations[trg_pop_name])
        self._edge_populations.append(edge_population)

    def build(self):
        self.build_nodes()
        self.build_recurrent_edges()

    def build_nodes(self):
        raise NotImplementedError()

    def build_recurrent_edges(self):
        raise NotImplementedError()

    def build_virtual_connections(self):
        raise NotImplementedError()

    @classmethod
    def from_config(cls, conf, **properties):
        """Generates a graph structure from a json config file or dictionary.

        :param conf: name of json config file, or a dictionary with config parameters
        :param properties: optional properties.
        :return: A graph object of type cls
        """
        network = cls(**properties)

        # The simulation run script should create a config-dict since it's likely to vary based on the simulator engine,
        # however in the case the user doesn't we will try a generic conversion from dict/json to ConfigDict
        if isinstance(conf, ConfigDict):
            config = conf
        else:
            try:
                config = ConfigDict.load(conf)
            except Exception as e:
                network.io.log_exception('Could not convert {} (type "{}") to json.'.format(conf, type(conf)))

        if not config.with_networks:
            network.io.log_exception('Could not find any network files. Unable to build network.')

        # TODO: These are simulator specific
        network.spike_threshold = config.spike_threshold
        network.dL = config.dL

        # load components
        for name, value in config.components.items():
            network.add_component(name, value)

        # load nodes
        gid_map = config.gid_mappings
        node_adaptor = network.get_node_adaptor('sonata')
        for node_dict in config.nodes:
            nodes = sonata_reader.load_nodes(node_dict['nodes_file'], node_dict['node_types_file'], gid_map,
                                             adaptor=node_adaptor)
            for node_pop in nodes:
                network.add_nodes(node_pop)

        # TODO: Raise a warning if more than one internal population and no gids (node_id collision)

        # load edges
        edge_adaptor = network.get_edge_adaptor('sonata')
        for edge_dict in config.edges:
            #target_network = edge_dict['target'] if 'target' in edge_dict else None
            #source_network = edge_dict['source'] if 'source' in edge_dict else None
            edges = sonata_reader.load_edges(edge_dict['edges_file'], edge_dict['edge_types_file'],
                                             adaptor=edge_adaptor)
            for edge_pop in edges:
                network.add_edges(edge_pop)

        return network

    @classmethod
    def from_manifest(cls, manifest_json):
        # TODO: Add adaptors to build a simulation network from model files downloaded celltypes.brain-map.org
        raise NotImplementedError()

    @classmethod
    def from_builder(cls, network):
        # TODO: Add adaptors to build a simulation network from a bmtk.builder Network object
        raise NotImplementedError()

