#!/usr/bin/env python
# -*- coding: utf-8 -*
'''Helper functions for icecube specific labels.
'''
from __future__ import print_function, division
import numpy as np
from icecube import dataclasses, MuonGun, simclasses
from icecube.phys_services import I3Calculator

from ic3_labels.labels.utils import geometry
from ic3_labels.labels.utils.muon import get_muon_energy_at_distance


def get_tau_energy_deposited(frame, convex_hull,
                             tau, first_cascade, second_cascade):
    '''Function to get the total energy a tau deposited in the
    volume defined by the convex hull.

    Parameters
    ----------
    frame : current frame
        needed to retrieve MMCTrackList and I3MCTree

    convex_hull : scipy.spatial.ConvexHull
        defining the desired convex volume

    tau : I3Particle
        tau.

    first_cascade : I3Particle
        hadrons from the first tau interaction

    second_cascade : I3Particle
        hadrons from the second tau interaction

    Returns
    -------
    energy : float
        Deposited Energy.
    '''
    if tau is None or first_cascade is None or second_cascade is None:
        return np.nan
    v_pos = (tau.pos.x, tau.pos.y, tau.pos.z)
    v_dir = (tau.dir.x, tau.dir.y, tau.dir.z)
    intersection_ts = geometry.get_intersections(convex_hull, v_pos, v_dir)

    # tau didn't hit convex_hull
    if intersection_ts.size == 0:
        return 0.0

    # tau hit convex_hull:
    #   Expecting two intersections
    #   What happens if track is exactly along edge of hull?
    #   If only one ts: track exactly hit a corner of hull?
    assert len(intersection_ts) == 2, 'Expected exactly 2 intersections'

    min_ts = min(intersection_ts)
    max_ts = max(intersection_ts)

    if min_ts <= 0 and max_ts >= 0:
        # starting track
        dep_en = first_cascade.energy
        # If the tau decays before exiting:
        # - Add the hadronic energy from the second cscd
        #   and the energy lost by the tau in the detector
        if max_ts >= tau.length:
            dep_en += tau.energy - get_muon_energy_at_distance(
                frame, tau, tau.length - 1e-6)
            dep_en += second_cascade.energy

        # If the tau exits the detector before decaying:
        # - Add the energy lost in the detector
        else:
            dep_en += tau.energy - get_muon_energy_at_distance(
                frame, tau, max_ts)

    if max_ts < 0:
        # tau created after the convex hull
        return 0.0

    if min_ts > 0 and max_ts > 0:
        # Incoming Track
        # Dont count the first cascade

        # If the tau decays before exiting
        # Add the second cascade energy
        if max_ts >= tau.length:
            dep_en = get_muon_energy_at_distance(frame, tau, min_ts) - \
                get_muon_energy_at_distance(frame, tau, tau.length - 1e-6)
            dep_en += second_cascade.energy
        # Otherwise just take the energy lost from the tau
        else:
            return get_muon_energy_at_distance(frame, tau, min_ts) - \
                get_muon_energy_at_distance(frame, tau, max_ts)


def get_nutau_interactions(frame):
    mctree = frame['I3MCTree']
    # Find all neutrinos InIce
    in_ice_neutrinos = []
    for part in mctree:
        if part.is_neutrino and part.location_type_string == 'InIce':
            in_ice_neutrinos.append(part)
    # The first one is the primary neutrino
    primary_nu = in_ice_neutrinos[0]

    daughters = mctree.get_daughters(primary_nu)

    tau = None
    first_cascade = None
    second_cascade = None
    for daughter in daughters:
        if daughter.type_string == 'TauMinus' or \
                daughter.type_string == 'TauPlus':
            tau = daughter
        if daughter.type_string == 'Hadrons':
            first_cascade = daughter

    try:
        tau_daughters = mctree.get_daughters(tau)
    except Exception as e:
        return primary_nu, tau, first_cascade, second_cascade
    else:
        for daughter in tau_daughters:
            if daughter.type_string == 'Hadrons':
                second_cascade = daughter
        return primary_nu, tau, first_cascade, second_cascade


def get_tau_labels(frame, convex_hull):
    labels = dataclasses.I3MapStringDouble()

    primary_nu, tau, first_cascade, second_cascade = get_nutau_interactions(
        frame)
    labels['MC_PrimaryInDetectorEnergyLoss'] = get_tau_energy_deposited(
        frame, convex_hull, tau, first_cascade, second_cascade)
    labels['MC_PrimaryEnergy'] = primary_nu.energy

    return labels
