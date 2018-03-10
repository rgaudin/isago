#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import logging

from flask import Flask
from flask import request
from flask import render_template
from babel.numbers import format_number

from isago import MATRIX, Calculator

LOCALE = "fr_FR"
CFA2KWH = "cfa2kwh"
KWH2CFA = "kwh2cfa"
METER_KINDS = ("single-phase", "three-phases")

logger = logging.getLogger(__name__)
app = Flask(__name__)


def get_meter_groups():
    groups = []
    for kind in METER_KINDS:
        mk = MATRIX[kind]
        group = {
            'kind': kind,
            'label': mk['label'],
            'amperages': [{'amperage': amp['amperage'],
                           'power': amp['power'],
                           'code': "{kind}_{amp}"
                           .format(kind=kind, amp=amp['amperage'])}
                          for amp in mk['amperage'].values()]
        }
        groups.append(group)
    return groups


@app.route("/", methods=['GET', 'POST'])
def home():
    context = {}
    context['conf'] = {}

    def validated_inputs(form_data):
        raw_meter = form_data.get('meter_conf').strip()
        kind, amp_str = raw_meter.split('_', 1)
        assert kind in METER_KINDS

        amperage = int(amp_str)
        assert str(amperage) in MATRIX[kind]['amperage'].keys()

        value_raw = request.form.get('value')
        value = float(value_raw.strip())
        previous_kwh_raw = request.form.get('previous_kwh')
        previous_kwh = float(previous_kwh_raw.strip()) \
            if previous_kwh_raw else 0

        operation = KWH2CFA if KWH2CFA in request.form else CFA2KWH
        assert operation in (KWH2CFA, CFA2KWH)

        return {
            'kind': kind,
            'amperage': amperage,
            'meter_conf': "{kind}_{amp}".format(kind=kind, amp=amperage),
            'value': value,
            'previous_kwh': previous_kwh,
            'operation': operation
        }

    context['groups'] = get_meter_groups()
    if request.method == 'POST':
        try:
            conf = validated_inputs(request.form)
        except Exception as exp:
            logger.exception(exp)
            context['error'] = "Incorrect Data: {}".format(exp)
        else:
            context['conf'] = conf
            calc = Calculator(conf['kind'], conf['amperage'],
                              conf['previous_kwh'])
            context['calculator'] = calc

            if conf['operation'] == CFA2KWH:
                amount = conf['value']
                cons = calc.consumption_for_amount(amount)
                nb_kwh = cons.nb_kwh
                average = calc.avg(nb_kwh, amount)

            elif conf['operation'] == KWH2CFA:
                nb_kwh = conf['value']
                cons = calc.consumption_for_kwh(nb_kwh)
                amount = calc.get_final(cons)

            average = calc.avg(nb_kwh, amount)
            context['consumption'] = cons
            context['summary'] = {
                'nb_kwh': nb_kwh,
                'amount': format_number(amount, locale=LOCALE),
                'average': format_number(average, locale=LOCALE),
            }

    # from pprint import pprint as pp ; pp(context)

    return render_template('home.html', **context)


if __name__ == '__main__':
    app.run()
