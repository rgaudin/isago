#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import copy
import logging
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Meter(object):

    SLICES = [50, 100, 200]

    def __init__(self, config):
        self.slices = []
        for k, v in config.items():
            setattr(self, k, v)

        for number in range(1, self.nb_slices + 1):
            self.slices.append(Slice(self, number))

    @property
    def nb_slices(self):
        return len(self.SLICES) + 1

    def get_verbose_phase(self):
        if self.nb_phase == 1:
            return "monophasé"
        elif self.nb_phase == 3:
            return "triphasé"

    def __str__(self):
        return "{phase} {amperage}A".format(
            phase=self.get_verbose_phase(), amperage=self.amperage
        )


with open("isago.json", "r") as fd:
    MATRIX = json.load(fd)


def get_meter(kind, amperage):
    config = MATRIX[kind]["amperage"][str(amperage)]
    return Meter(config)


def std_round(amount):
    if float(amount).is_integer():
        return round(amount)
    return round(amount, 2)


class Slice(object):
    def __init__(self, meter, slice_number):
        assert isinstance(meter, Meter)
        assert slice_number in range(1, 5)
        self.number = slice_number
        self.meter = meter

    def __str__(self):
        return "{meter} / TR{slice}".format(meter=self.meter, slice=self.number)

    @property
    def index(self):
        return self.number - 1

    @property
    def ppkwh(self):
        return self.meter.ppkwh[self.index]

    @property
    def vat_rate(self):
        if isinstance(self.meter.vat, (int, float)):
            return self.meter.vat
        return self.meter.vat[self.index]

    @property
    def maintpkwh(self):
        if isinstance(self.meter.maint, (int, float)):
            return self.meter.maint
        return self.meter.maint[self.index]

    @property
    def size(self):
        if self.index == 0:
            return std_round(self.meter.SLICES[self.index])
        if self.index == len(self.meter.SLICES):
            return None
        return std_round(
            self.meter.SLICES[self.index] - self.meter.SLICES[self.index - 1]
        )

    @property
    def lightspkwh(self):
        return self.meter.lights

    def get_lights_cost(self, kwh):
        """ not slice-related per say """
        return std_round(self.meter.lights * kwh)

    def get_price(self, nb_kwh):
        return std_round(self.ppkwh * nb_kwh)

    def get_vat(self, nb_kwh):
        return std_round(self.vat_rate * self.get_price(nb_kwh))

    def get_cost(self, nb_kwh):
        return std_round(sum([self.get_price(nb_kwh), self.get_vat(nb_kwh)]))

    def get_lights(self, nb_kwh):
        return std_round(self.lightspkwh * nb_kwh)

    def get_total_cost(self, nb_kwh):
        return std_round(
            sum([self.get_price(nb_kwh), self.get_vat(nb_kwh), self.get_lights(nb_kwh)])
        )

    def get_maint(self, nb_kwh):  # already included in price
        return std_round(self.maintpkwh * nb_kwh)

    def get_max_price(self):
        return None if self.size is None else self.get_price(self.size)

    def get_max_vat(self):
        return None if self.size is None else self.get_vat(self.size)

    def get_max_cost(self):
        return None if self.size is None else self.get_cost(self.size)

    def get_max_total_cost(self):
        return None if self.size is None else self.get_total_cost(self.size)

    def get_max_maint(self):
        return None if self.size is None else self.get_maint(self.size)

    def get_kwh_for(self, amount):
        return std_round(amount / self.get_total_cost(1))


class SliceUsage(object):
    def __init__(self, nb_kwh, price, vat, maint, cost, mslice):
        self.nb_kwh = std_round(nb_kwh)
        self.price = std_round(price)
        self.vat = std_round(vat)
        self.maint = std_round(maint)
        self.cost = std_round(cost)
        self.slice = mslice

    def __str__(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        return {
            "nb_kwh": self.nb_kwh,
            "price": self.price,
            "vat": self.vat,
            "maint": self.maint,
            "cost": self.cost,
        }


class Consumption(object):
    def __init__(self, meter, nb_kwh=0, previous_slice=1, previous_kwh=0):
        self.meter = meter
        self.nb_kwh = nb_kwh
        self.slices = {}

        # previous-consumption
        self.previous_slice = previous_slice
        self.previous_kwh = previous_kwh

        self.calculate()

    def get_current_position(self):
        su = None
        for meter_slice in self.meter.slices:

            if meter_slice.number not in self.slices.keys():
                su = None
                break

            su = self.slices[meter_slice.number]
            if meter_slice.size is not None and meter_slice.size > su.nb_kwh:
                break

        existing = su.nb_kwh if su is not None else 0
        return {"slice": meter_slice.number, "existing": existing}

    def calculate(self):
        # ventilate consumption accross slices with SliceUage
        remaining_kwh = copy.copy(self.nb_kwh)
        previous_handled = False
        for meter_slice in self.meter.slices:

            # skip slices already filled by previous consumption
            if meter_slice.number < self.previous_slice:
                continue

            # skip additional slices if we're done
            if remaining_kwh <= 0:
                continue

            # record size of this slice
            ms_size = meter_slice.size

            # if not last slice, remove from it the already consumed kwh
            if ms_size is not None and not previous_handled:
                ms_size -= self.previous_kwh
                previous_handled = True

            if ms_size is not None and remaining_kwh > ms_size:
                slice_kwh = ms_size
            else:
                slice_kwh = remaining_kwh

            remaining_kwh -= slice_kwh
            su = SliceUsage(
                nb_kwh=slice_kwh,
                price=meter_slice.get_price(slice_kwh),
                vat=meter_slice.get_vat(slice_kwh),
                maint=meter_slice.get_maint(slice_kwh),
                cost=meter_slice.get_cost(slice_kwh),
                mslice=meter_slice,
            )
            self.slices[meter_slice.number] = su

        # add public clights cost
        self.lights = self.get_lights_cost(self.nb_kwh)

    def get_lights_cost(self, kwh):
        return std_round(self.meter.lights * kwh)

    def get_cost(self):
        return std_round(sum([self.lights] + [sl.cost for sl in self.slices.values()]))

    def to_dict(self):
        return {
            "nb_kwh": self.nb_kwh,
            "lights": self.lights,
            "slices": {number: su.to_dict() for number, su in self.used_slices.items()},
            "cost": self.get_cost(),
        }

    @property
    def used_slices(self):
        return {
            ms.number: self.slices[ms.number]
            for ms in self.meter.slices
            if ms.number in self.slices.keys()
        }

    def get_kwh_for(self, amount):
        # ventilate amount accross slices with SliceUage
        remaining_amount = copy.copy(amount)

        previous_handled = False
        slices_max = 0
        total_kwh = 0

        for meter_slice in self.meter.slices:
            # skip slices already filled by previous consumption
            if meter_slice.number < self.previous_slice:
                continue

            # skip additional slices if we're done
            if remaining_amount <= 0:
                break

            # record size of this slice
            ms_size = meter_slice.size

            # if not last slice, remove from it the already consumed kwh
            if ms_size is not None and not previous_handled:
                ms_size -= self.previous_kwh
                previous_handled = True

            # consider this slice will be filled
            if ms_size is not None:
                total_kwh += ms_size

            # record max amount for this slice
            ms_max = meter_slice.get_max_total_cost()
            if ms_max is not None:
                # consider this slice will be paid in full
                slices_max += ms_max

            # if price to pay this sum is above budget, break
            if remaining_amount <= slices_max:
                break

        # remove sum of all previous
        remaining_amount -= slices_max
        # print("remaining_amount", remaining_amount)

        last_slice_kwh = meter_slice.get_kwh_for(remaining_amount)
        # print("last_slice_kwh", last_slice_kwh)

        total_kwh += last_slice_kwh

        return total_kwh


class Calculator(object):
    def __init__(self, nb_phase, amperage, previous_kwh):
        self.meter = get_meter(nb_phase, amperage)
        self.previous_cons = Consumption(self.meter, previous_kwh)
        self.previous_position = self.previous_cons.get_current_position()
        self.cons = None

    @property
    def previous_kwh(self):
        return self.previous_cons.nb_kwh

    @classmethod
    def get_stamp_cost(cls):
        return MATRIX["stamp"]

    @classmethod
    def avg(cls, kwh, amount):
        return round(amount / kwh, 2) if kwh > 0 else 0

    @classmethod
    def round_final_amount(cls, amount):
        return int(round(amount, -1))

    @classmethod
    def get_final(cls, consumption):
        return cls.round_final_amount(cls.get_stamp_cost() + consumption.get_cost())

    def consumption_for_kwh(self, nb_kwh):
        cons = Consumption(
            meter=self.meter,
            nb_kwh=nb_kwh,
            previous_slice=self.previous_position["slice"],
            previous_kwh=self.previous_position["existing"],
        )
        return cons

    def consumption_for_amount(self, amount):

        remaining_amount = copy.copy(amount)

        # remove stamp cost
        remaining_amount -= self.get_stamp_cost()

        cons = Consumption(
            meter=self.meter,
            previous_slice=self.previous_position["slice"],
            previous_kwh=self.previous_position["existing"],
        )
        nb_kwh = cons.get_kwh_for(remaining_amount)
        cons.nb_kwh = nb_kwh
        cons.calculate()

        return cons
