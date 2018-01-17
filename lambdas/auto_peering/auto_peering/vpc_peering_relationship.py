from botocore.exceptions import ClientError


class VPCPeeringRelationship(object):
    def __init__(self, vpc1, vpc2, ec2_resources, logger):
        self.vpc1 = vpc1
        self.vpc2 = vpc2
        self.ec2_resources = ec2_resources
        self.logger = logger

    def __peering_connection_for(self, vpc1, vpc2):
        ec2_resource = self.ec2_resources.get(vpc1.region)

        return next(
            iter(ec2_resource.vpc_peering_connections.filter(
                Filters=[{'Name': 'accepter-vpc-info.vpc-id',
                          'Values': [vpc1.id]},
                         {'Name': 'requester-vpc-info.vpc-id',
                          'Values': [vpc2.id]}])),
            None)

    def fetch(self):
        peering_connection = self.__peering_connection_for(
            self.vpc1, self.vpc2)
        if peering_connection:
            return peering_connection

        peering_connection = self.__peering_connection_for(
            self.vpc2, self.vpc1)
        if peering_connection:
            return peering_connection

        return None

    def provision(self):
        vpc1_id = self.vpc1.id
        vpc2_id = self.vpc2.id
        vpc2_region = self.vpc2.region

        self.logger.debug(
            "Requesting peering connection between: '%s' and: '%s'.",
            vpc1_id, vpc2_id)
        requester_vpc_peering_connection = self. \
            vpc1.request_vpc_peering_connection(PeerVpcId=vpc2_id,
                                                PeerRegion=vpc2_region)

        try:
            self.logger.debug(
                "Accepting peering connection between: '%s' and: '%s'.",
                vpc1_id, vpc2_id)
            ec2_resource = self.ec2_resources.get(vpc2_region)
            acceptor_vpc_peering_connection = next(iter(
                ec2_resource.vpc_peering_connections.filter(
                    VpcPeeringConnectionIds=[
                        requester_vpc_peering_connection.id
                    ])), None)
            acceptor_vpc_peering_connection.accept()
        except ClientError as error:
            self.logger.warn(
                "Could not accept peering connection. This may be because one "
                "already exists between '%s' and: '%s'. Error was: %s.",
                vpc1_id, vpc2_id, error)
            requester_vpc_peering_connection.delete()

    def destroy(self):
        vpc_peering_connection = self.fetch()
        if vpc_peering_connection:
            self.logger.debug(
                "Destroying peering connection between: '%s' and: '%s'",
                vpc_peering_connection.requester_vpc.id,
                vpc_peering_connection.accepter_vpc.id)
            vpc_peering_connection.delete()
        else:
            self.logger.debug(
                "No peering connection to destroy between: '%s' and: '%s'",
                self.vpc1.id,
                self.vpc2.id)

    def perform(self, action):
        getattr(self, action)()

    def _to_dict(self):
        return {
            'vpcs': frozenset([self.vpc1, self.vpc2])
        }

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._to_dict() == other._to_dict()
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(sorted(self._to_dict().items())))
