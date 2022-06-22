"""
This is the implementation of truck platooning analogy
several algorithm are implemented here
1. Lane changing algorithm
2. Gap creation algorithm
3. Leader election using bull algorithm
"""

from math import sin, cos, sqrt, atan2, radians
import numpy as np
import time
import json
import requests
from random import randint
from threading import Timer

def goto(linenum):
    """
    This is the code that implements the goto functionality incase a block of code needs to be implemented
    over again
    :param linenum:
    :return:
    """
    global line
    line = linenum


class Car:
    """
    This is the class that keeps the details of a car/truck. Each truck car has a class like this

    :param lane:This is the lane that the car is in
    :param speed:This is the speed of the car
    :param role:This is the role of the car. The roles are leader, which is
        the car that processes the request,preceder , which is the car that
        precedes the car asking to change lane, follower, which is the car
    :param vehicleid: This is a unique id representing a car
    """
    def __init__(self, name, port, laneid, speed, long, lat,  routename, vehicleid=None):
        self.name=name
        self.port=port
        self.laneid=laneid
        self.speed=speed
        self.vehicleid=vehicleid
        self.long=long
        self.lat=lat
        self.route=routename
        self.lanechangestatus="no change"

class platoon:
    """
    This is the class that keeps the details of a platoon
    All functions of the platoon such as election, joining, leaving, etc are held in this class
    Testing of the election algorithm of the platoon can be found
    at: https://isuruuy.medium.com/electing-master-node-in-a-cluster-using-bully-algorithm-b4e4fa30195c
    """
    def __init__(self, size, route, thresholdspeed):
        """
        
        :param size: This is the size of the platoon
        :param route: This is route that platoon is taking
        :param thresholdspeed:
        """""
        self.size=size
        self.route=route
        self.threshspeed=thresholdspeed
    def join(self, car):
        """
        This is the function the truck calls if they want to leave the platoon
        :param car: The class with car details
        :return:
        """
        url = "http://localhost:8500/v1/agent/service/register"
        data = {
            "Name": car.name,
            "ID": str(car.vehicleid),
            "port": car.port,
            "check": {
                "name": "Check Counter health %s" % car.port,
                "tcp": "localhost:%s" % car.port,
                "interval": "10s",
                "timeout": "1s"
            }
        }
        put_request = requests.put(url, json=data)
        return put_request.status_code

    def leave(self, car):
        """
        This is the function that a car calls if it wants to leave a platoon

        :param car:
        :return:
        """
        url = "http://localhost:8500/v1/agent/service/register"
        data = {
            "Name": car.name,
            "ID": str(car.vehicleid),
            "port": car.port,
            "check": {
                "name": "Check Counter health %s" % car.port,
                "tcp": "localhost:%s" % car.port,
                "interval": "10s",
                "timeout": "1s"
            }
        }
        put_request = requests.delete(url, json=data)
        return put_request.status_code

    def check_health_of_the_service(self, service):
        print('Checking health of the %s' % service)
        url = 'http://localhost:8500/v1/agent/health/service/name/%s' % service
        response = requests.get(url)
        response_content = json.loads(response.text)
        aggregated_state = response_content[0]['AggregatedStatus']
        service_status = aggregated_state
        if response.status_code == 503 and aggregated_state == 'critical':
            service_status = 'crashed'
        print('Service status: %s' % service_status)
        return service_status

    # get ports of all the registered nodes from the service registry

    def get_ports_of_nodes(self):
        ports_dict = {}
        response = requests.get('http://127.0.0.1:8500/v1/agent/services')
        nodes = json.loads(response.text)
        for each_service in nodes:
            service = nodes[each_service]['Service']
            status = nodes[each_service]['Port']
            key = service
            value = status
            ports_dict[key] = value
        self.portdict=ports_dict
        return ports_dict

    def get_higher_nodes(self, node_details, node_id):
        higher_node_array = []
        for each in node_details:
            if each['node_id'] > node_id:
                higher_node_array.append(each['port'])
        self.higher_node_array=higher_node_array
        return higher_node_array

    # this method is used to send the higher node id to the proxy
    def election(self, higher_nodes_array, node_id):
        status_code_array = []
        for each_port in higher_nodes_array:
            url = 'http://localhost:%s/proxy' % each_port
            data = {
                "node_id": node_id
            }
            post_response = requests.post(url, json=data)
            status_code_array.append(post_response.status_code)
        if 200 in status_code_array:
            return 200

    # this method returns if the cluster is ready for the election
    def ready_for_election(self, ports_of_all_nodes, self_election, self_coordinator):
        coordinator_array = []
        election_array = []
        node_details = self.get_details(ports_of_all_nodes)

        for each_node in node_details:
            coordinator_array.append(each_node['coordinator'])
            election_array.append(each_node['election'])
        coordinator_array.append(self_coordinator)
        election_array.append(self_election)

        if True in election_array or True in coordinator_array:
            self.ready_for_election = False
            return False

        else:
            self.ready_for_election = True
            return True

    # this method is used to get the details of all the nodes by syncing with each node by calling each nodes' API.
    def get_details(self, ports_of_all_nodes):
        node_details = []
        for each_node in ports_of_all_nodes:
            url = 'http://localhost:%s/nodeDetails' % ports_of_all_nodes[each_node]
            data = requests.get(url)
            node_details.append(data.json())
        self.node_details=node_details
        return node_details

    # this method is used to announce that it is the master to the other nodes.
    def announce(self, coordinator):
        all_nodes = self.get_ports_of_nodes()
        data = {
            'coordinator': coordinator
        }
        for each_node in all_nodes:
            url = 'http://localhost:%s/announce' % all_nodes[each_node]
            print(url)
            requests.post(url, json=data)


class Lane_Change:

    def __init__(self,platoon):
        platoonsize=len(platoon.port)
        self.platoonsize=platoonsize

    def change_lane(self, car1, car2, car3, car4, car5,route):
        """
        This is the function that implements lane change algorithm
        :param car1: This is the preceding car in the platoon
        :param car2: This is the tailing car in the platoon
        :param car3: This is the preceding car in the target lane
        :param car4: This is the tailing car in the target lane
        :param car5: This is the car requesting to change lane
        :return:
        """
        a=abs(self.calculate_distance(car5.lat, car5.long, car3.lat, car3.long))
        b=abs(self.calculate_distance(car5.lat, car5.long, car4.lat, car4.long))
        state1=self.check_space(a,b)

        # The algorithm starts by checking desirability for lane lane change
        mandatory_change, desire, desirevalue_target_lane=self.lane_change_desire_necessity(car5,route,car3.laneid)
        if mandatory_change=='True':
            print('Mandatory change.Checking space...')
            goto(2)

            if line==2:
                state1 = self.check_space(a, b)
                if state1==True:
                    print('space for lane change available...')
                    car5.lanechangestatus='in progress'
                else:
                    while state1==False:
                        state1 = self.check_space(a, b)
                        goto(2)
            self.gap_creation(car5, car1, car3)
        else:
            if desirevalue_target_lane>0.5:
                goto(2)
                self.gap_creation(car5, car1, car3)
            else:
                print('Lane changing is not necessary')

        if state1==True:
            print("Passed State-1 test:There is ample space for lane changing")
            state2=self.check_speed(car5.speed, car4.speed)
            if state2==True:
                print("Passed State-2 test: The ")
                state3=3
            else:
                exit
                print('Failed State-2 test:')


        else:
            exit
            print('Failed State-1:There is no ample space for lane changine. Try again after sometime')

    def check_space(self, a, b=None, allowed_distance=None):
        """
        This is the function that checks whether there is enough space for lane changing in the
            lane changing algorithm
        :param a: This is the distance between the car that requests to change the lane and the
            that ahead of it in the target lane
        :param b: This is the distance between the car requesting to change lane and the car behind it
            in the target lane. This can be none for Gap algorithm
        :return: Return True if the space is ample for lane changing and False otherwise
        """
        if allowed_distance==None:
            allowed_distance=50
        else:
            allowed_distance=allowed_distance
        if a>=allowed_distance:
            if b is not None:
                if b>=allowed_distance:
                    return True
                else:
                    return False
            else:
                return True
        else:
            return False
    def check_speed(self, self_speed, preceded_speed, threshold_speed=None):
        """
        This is the function that checks whether the preceded car in the target lane has a higher speed
            or that equal to the speed of the platoon
        :param self_speed: This is the speed of the car that sends the request to change the lane
        :param preceded_speed: This is the speed of the preceded car in the target lane
        :return: Returns true or false of whether the car should change lane
        """
        if preceded_speed>threshold_speed:
            return False

        else:
            if self_speed<=preceded_speed:
                return False
            else:
                if self_speed>platoon.threshspeed:
                    return False
                else:
                    return True

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        This is the function that calculates the distance between two cars/two functions
        :param lat1: This is the latitude of the first car
        :param lat2: This is the latitude of the second car
        :param lon1: This is the longitude of the first car
        :param lon2: This is the longitude of the second car
        :return: the distance between the two vehicles
        """
        # approximate radius of earth in km
        R = 6373.0

        lat1 = radians(lat1)
        lon1 = radians(lon1)
        lat2 = radians(lat2)
        lon2 = radians(lon2)

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c
        return distance

    def lane_change_desire_necessity(self, car, route, laneid):
        """
        This is the function that calculates whether it is necessary to change the lane or not.
        It returns True if changing of lane(s) is viable
        :return:
        """

        def dkr(car, route, laneid):
            """
            This is the function that calculates the desire to change
            :param car: This is the class with car details
            :param route: This is the class with route details
            :param laneid: This is the laneid or the target lane
            :return: returns whether the change is desirable and the desire value
            """
            x0 = 200  # This is the avaailable look distance
            lane = route[laneid]
            nk = self.path_distance(lane.lane_ending_latitude, lane.lane_ending_longitude, car.lat, car.long)
            xk = nk
            tk = xk / car.speed
            desire_based_on_distance = 1 - (xk / (nk * x0))
            desire_based_on_time = 1 - (tk / (nk * x0))
            testarray = [desire_based_on_distance, desire_based_on_time, 0]
            desire = np.argmax(testarray)
            desirevalue = np.max(testarray)

            if desire == 0:
                change_desirable = 'Yes'
                print('The desire is based on distance. The platoon is moving at a relatively low speed')
            elif desire == 1:
                change_desirable = "Yes"
                print('The desire is based on time. The platoon is moving at a relatively high speed')
            else:
                change_desirable = 'No'
                print('There is no desire to change or change or lane is undesirable')
            return change_desirable, desirevalue

        def mandatory_change(desirevalue_platoon_lane, desirevalue_target_lane):
            """
            This is the function that checks for mandatory change
            :param desirevalue_platoon_lane: This is the desire value of the platoon lane
            :param desirevalue_target_lane:  This is the desire value of the target lane
            :return: It returns desire for mandatory change and the 'boolean of mandatory change
            """
            if desirevalue_platoon_lane > desirevalue_target_lane:
                mandatory_change = "True"
                desire = desirevalue_platoon_lane
            elif desirevalue_platoon_lane == desirevalue_target_lane:
                mandatory_change = "False"
                desire = desirevalue_platoon_lane
            elif desirevalue_platoon_lane < desirevalue_target_lane:
                mandatory_change = "False"
                desire = 0
            else:
                desire = 0
            return mandatory_change, desire
        if laneid<0:
            exit()
            print('Invalid lane ID. Lane change aborted')
        elif laneid>len(route.lanes):
            print('The lane does not exist. Lane change aborted')
        else:
            #We check whether the desire is mandatory
            change_desirable_target_lane, desirevalue_target_lane=dkr(car, route, laneid)
            change_desirable_platoon_lane, desirevalue_platoon_lane = dkr(car, route, car.laneid)
            if change_desirable_platoon_lane=='Yes':
                if change_desirable_target_lane=="Yes":
                    mandatory_change, desire=mandatory_change(desirevalue_platoon_lane, desirevalue_target_lane)
                else:
                    mandatory_change, desire = mandatory_change(desirevalue_platoon_lane, desirevalue_target_lane)
            else:
                mandatory_change, desire = mandatory_change(desirevalue_platoon_lane, desirevalue_target_lane)
        return mandatory_change, desire, desirevalue_target_lane


    def path_distance(self, pathlat,pathlong, carlat, carlong):
        """
        This is the function that uses googlemaps API(Openstreetmap API) to calculate the remaining
            distance for the lane and the route.
            This function may also be used to calculate whether the lane and route have the same length
            or the lane ends before the route.
        :param path: These are the coordinates of a lane or a route
        :param car: these are the coordinates of a car that wants to change lane(we use the last car of a
            platoon as the reference
        :return: the distance
        """
        try:
            try:
                import requests
                import json  # call the OSMR API
                from geopy import distance

                d = distance.distance((pathlat, pathlong),
                                      (carlat, carlong))
                return (abs(getattr(d, "km")*1000))


            except:
                #This works incase the google API fails
                d=self.calculate_distance(pathlat, pathlong, carlat, carlong)
                return abs(d)
        except:
            exit
            print('System Error')

    def gap_creation(self, car1, car2, car3):
        """
        This is the function that implements gap creation algorithm once the
        :param car1: This is the last car is the platoon
        :param car2: This is the first car in the platoon
        :param car3: This is the preceding car in the target lane
        :return:success message
        """
        a=self.calculate_distance(car3.lat, car3.long, car2.lat, car2.long)
        if car1.lanechangestatus=='complete':

            if car2.lanechangestatus=='in progress':
                goto(1)
                if line==1:
                    space=self.check_space(a)
                    if space==True:
                        print("Lane change safe")
                        condtion='safe'
                    else:
                        print("Lane change not safe")
                        print('decelerating')
                        #decelerate until its safe for all trucks to change lane
                        while space==False:
                            deceleration=(car2.speed-5)/0.016666
                            dv=deceleration*0.0166666
                            time.sleep(60)
                            car2.speed=car2.speed-dv
                        print('decelation complete. Safe to change lane')
                        condition='safe'
            elif car2.lanechangestatus=='complete':
                print("Lane change completed safely")
            elif car2.lanechange=='':
                print("Lane change for the lead truck not initiated. Initiate")
                goto(1)
            else:
                print('there is no desire to change lane')
        else:
            print("Gap algorithm not needed")
    def __getattr__(self, item):








class Lane:
    """
    This is the class that keeps the details of a lane
    The details of a lane include: latitude,longitude(start and end) and id

    """
    def __init__(self,lanelatstart, lanelongstart, lanelatend, lanelongend, laneid):
        """
        :param lanelongstart: This is the longitude where the lane starts
        :param lanelatstart: This is the latitude where the lane starts
        :param lanelongend: This is the logitude where the lane ends
        :param lanelatend: This is the latitude that the lane ends
        :param laneid: This is the id of the lane. If a route has five lanes, then the first lane shall have
        id=1 and the last lane shall have id=5
        """
        self.lane_starting_latitude=lanelatstart
        self.lane_starting_longitude=lanelongstart
        self.lane_ending_latitude=lanelatend
        self.lane_ending_longitude=lanelongend
        self.id=laneid
class route(Lane):
    """
    This is the class that carries the details of the
    """
    def __init__(self,routelatstart, routelongstart, routelatend, routelongend,routename, NOL=None):
        """
        :param routelongstart: This is the longitude where the route starts
        :param routelatstart: This is the latitude where the route starts
        :param routelongend: This is the logitude where the route ends
        :param routelatend: This is the latitude that the route ends
        :param routename: This is route name
        :param NOL:This is the number of lanes in the route. If not specified, it is
        assumed that the route has one lane
        """
        self.route_starting_latitude=routelatstart
        self.route_starting_longitude=routelongstart
        self.route_ending_latitude=routelatend
        self.route_ending_longitude=routelongend
        self.name=routename
        if NOL is None:
            self.NOL=1
        else:
            self.NOl=NOL
        self.lanes={}

    def add_lane(self, lanelatstart, lanelongstart, lanelatend, lanelongend):
        id=len((self.lanes).keys)
        if id<self.NOL:
            lane=Lane(lanelatstart, lanelongstart, lanelatend, lanelongend, id+1)
            lanes={id+1: lane}
            self.lanes.update(lanes)
        else:
            exit()
            print("The route has list of lanes fully registered")
lane=Lane_Change(getattr(platoon))


