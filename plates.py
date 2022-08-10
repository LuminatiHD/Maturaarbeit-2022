"""Alles zu den Klassen Plate und World"""
from __future__ import annotations
import numpy as np
from typing import Literal, Iterable
from shapely.geometry import Polygon, Point
import random as rand
from assets import getPointOnLinesegment, organic_border


class Plate():
    """Ist definiert als eine liste an vertices, einem PlatePoint, sowie einem drift-vektor"""
    def __init__(self, point: np.ndarray[int, int], vertices: Iterable[tuple[int, int]],
                 PType: Literal["K", "O"], drift: np.array = np.array((0, 0))):
        self.vertices = tuple(tuple(i) for i in vertices) # gibt man direkt np.arrays ins tuple, dann funktioniert tuple.index nicht mehr
        self.Plate_point = point
        self.drift_vector = drift
        if not type(PType) is str or not PType.upper() in ["K", "O"]:
            raise TypeError("PType ist entweder 'K' oder 'O'")
        else:
            self.PType = PType

    def __repr__(self):
        pass

    def split(self, point:np.ndarray[int|float, int|float], t:float)  -> tuple[Plate, Plate]:
        """Trennt die Platte entlang einer Mittelsenkrechte zwischen dem Plattenpunkt und dem gegebenen punkt point.
        Platte bleibt intakt, gibt 2 Platten zurück
        :param point: siehe oben
        :param t: gibt an, wann die Platte gebrochen ist."""
        if not Polygon(self.vertices).contains(Point(point)):
            raise ValueError("Point is located outside the Plate.")
        P = self.Plate_point
        R = point
        midpoint = R + (P-R)*0.5
        vector:np.ndarray[int|float, int|float] = P-R
        # das rotiert den Vektor um 90°
        vector[0], vector[1] = -vector[1], vector[0]

        # loopt über alle Paare von Punkten -> Ecken, und sucht, welche Ecken die Mittelsenkrechte schneidet.
        Border_to_Poly = dict()
        for i in range(len(self.vertices)):
            E1 = self.vertices[i-1]
            E2 = self.vertices[i]
            Q = getPointOnLinesegment(midpoint, vector, np.array(E1), np.array(E2))
            if len(Border_to_Poly)<2 and Q is not None:
                # np.arrays sind mutable -> nicht hashable -> kann man nicht als key gebrauchen
                Border_to_Poly[tuple(Q)] = (E1, E2)

        # Die Platten werden wieder zusammengesetzt
        Border = organic_border(np.array(list(Border_to_Poly.keys())[0]), np.array(list(Border_to_Poly.keys())[1]))

        start_P = Border[0]
        end_P = Border[-1]
        Plate1 = []
        Plates = []

        walker = Border_to_Poly[tuple(start_P)][0]
        # um herauszufinden, wie genau der walker die Liste absuchen soll, muss er zuerst wissen, wo auf der Liste er sich befindet
        index = self.vertices.index(tuple(walker))

        other_p = np.array(Border_to_Poly[tuple(start_P)][1])
        other_p_index = self.vertices.index(tuple(other_p))
        if (index-other_p_index) % len(self.vertices) == 1:
            direction = 1
        else:
            direction = -1
        # bevor der Walker losläuft, muss er wissen, ob er die Liste vorwärts oder rückwärts ablaufen muss. Das hängt ganz
        # davon ab, wo sich sein "Bruderpunkt" befindet (der Punkt, wo sich zwischen ihm und dem Punkt die Ecke der Grenze befindet).
        # TL/DR: liegt der Bruderpunkt indexmässig vor ihm, muss der Walker rückwärts die Liste ablaufen und vice verse.

        while len(Plates) < 2:
            Plate1.append(walker)
            # der Walker läuft vom einen Ende der Plattengrenze über die Vertices der alten Platte zum anderen Ende.
            # bei jedem Schritt schaut es nach, ob es an einem der Eckpunkte gelangt ist, zwischen welchen sich der Endpunkt befindet.
            # wenn das der Fall ist, weisst der Walker, dass er direkt vom Endpunkt über den Pfad definiert in der Liste "Border" wieder hin zum Startpunkt kann,
            # um damit seine Rundtour beendet zu haben -> das Polygon vervollständigt hat.
            # Der Walker läuft jedoch noch weiter, um auch die zweite Hälfte der Platte zu definieren.

            # für a in b-statements darf das objekt in question auch nicht ein np.array sein, da np.array == np.array nicht ein bool, sondern ein bool-array zurückgibt.
            if tuple(walker) in Border_to_Poly[tuple(end_P)]:
                if end_P == Border[0]:
                    Plate1.extend(Border)
                else:
                    # wenn der Endpunkt am anderen Ende der Grenzlinie ist, muss die Liste reversed werden bevor man sie dem
                    # Polygon hinzugibt, da man ja um zum anderen Ende der Grenze zu kommen die Liste RÜCKWÄRTS ablaufen muss.
                    Plate1.extend(Border[::-1])

                Plates.append(Plate1)
                start_P, end_P = end_P, start_P # nachdem man vom einen Ende zum anderen gekommen ist, muss man auch noch vom anderen Ende zum einen kommen.
                Plate1 = []

            # der Walker geht ein Schritt weiter. Falls er am Ende der Liste angelangt ist, kann er einfach hinten wieder anfangen.
            index+=direction
            walker = self.vertices[index%len(self.vertices)]

        # die Platten werden fertiggestellt. Dazu werden auch den jeweiligen Driftvektor und den Plattenpunkt zugeteilt
        out = []
        for plate_vertices in Plates:
            # Die Zuteilung des Plattenpunktes ist relativ einfach, da sich der Plattenpunkt
            # ja innerhalb der Platte befinden muss.
            if Polygon(plate_vertices).contains(Point(P)):
                plate_point = P
            else:
                plate_point = R

            drift_vector = plate_point-midpoint
            # der Vektor wird normalisiert und mit t multipliziert
            drift_vector *= t/np.linalg.norm(drift_vector)

            out.append(Plate(point=plate_point, vertices=plate_vertices, PType=self.PType, drift=drift_vector+self.drift_vector))

        return tuple((out[0], out[1]))



class World():
    """Der Container für die Platten"""
    def __init__(self, size:tuple[int, int], plates:Iterable[Plate] | None = None):
        self.size = size
        if plates:
            self.plates = list(plates)
        else:
            self.plates = [Plate(point = np.array((size[0]/2, size[1]/2)),
                                 vertices=((0, 0), (0, size[1]), (size[0], size[1]), (size[0], 0)),
                                 PType="K")]

        self.age = 1

    def getPlate(self, point:np.ndarray[int, int]) -> Plate:
        """gibt an, in welcher Platte der angegebene Punkt enthalten ist."""
        selected_plate = None
        # es werden alle plates durchgeloopt bis die Platte gefunden ist, in der der Punkt enthalten ist.
        for plate in self.plates:
            if Polygon(plate.vertices).contains(Point(point)):
                selected_plate = plate
                return selected_plate

        # es kann theoretisch möglich sein, dass der Punkt in keiner Plate enthalten ist
        if not selected_plate:
            raise Exception("Point is not contained in any Plate")

    def split(self, point:np.ndarray[int|float, int|float]|None = None) -> None:
        if point is None:
            point = np.array((rand.uniform(0, self.size[0]), rand.uniform(0, self.size[1])))
            # wurde kein Punkt spezifiziert, generiert das Programm einen zufälligen Punkt

        selected_plate = self.getPlate(point)

        # die alte Platte wird gesplittet. Dies gibt 2 neue Platten zurück.
        new_plates = selected_plate.split(point, self.age)

        # die alte Platte wird durch die neuen Platten ersetzt
        self.plates.remove(selected_plate)
        self.plates.extend(new_plates)

        self.age-= rand.uniform(0, self.age/2)

    def getPointHeight(self, point:np.ndarray[int|float, int|float]) -> float|int:
        pass
