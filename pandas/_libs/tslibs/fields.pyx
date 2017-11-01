# -*- coding: utf-8 -*-
# cython: profile=False
# cython: linetrace=False
# distutils: define_macros=CYTHON_TRACE=0
# distutils: define_macros=CYTHON_TRACE_NOGIL=0
"""
Functions for accessing attributes of Timestamp/datetime64/datetime-like
objects and arrays
"""

cimport cython
from cython cimport Py_ssize_t

import numpy as np
cimport numpy as np
from numpy cimport ndarray, int64_t, int32_t, int8_t
np.import_array()


from np_datetime cimport pandas_datetimestruct, dt64_to_dtstruct

from datetime cimport (
    days_per_month_table,
    is_leapyear,
    dayofweek)

cimport util

cdef int64_t NPY_NAT = util.get_nat()


def build_field_sarray(ndarray[int64_t] dtindex):
    """
    Datetime as int64 representation to a structured array of fields
    """
    cdef:
        Py_ssize_t i, count = 0
        pandas_datetimestruct dts
        ndarray[int32_t] years, months, days, hours, minutes, seconds, mus

    count = len(dtindex)

    sa_dtype = [('Y', 'i4'),  # year
                ('M', 'i4'),  # month
                ('D', 'i4'),  # day
                ('h', 'i4'),  # hour
                ('m', 'i4'),  # min
                ('s', 'i4'),  # second
                ('u', 'i4')]  # microsecond

    out = np.empty(count, dtype=sa_dtype)

    years = out['Y']
    months = out['M']
    days = out['D']
    hours = out['h']
    minutes = out['m']
    seconds = out['s']
    mus = out['u']

    for i in range(count):
        dt64_to_dtstruct(dtindex[i], &dts)
        years[i] = dts.year
        months[i] = dts.month
        days[i] = dts.day
        hours[i] = dts.hour
        minutes[i] = dts.min
        seconds[i] = dts.sec
        mus[i] = dts.us

    return out


@cython.wraparound(False)
@cython.boundscheck(False)
def get_date_name_field(ndarray[int64_t] dtindex, object field):
    """
    Given a int64-based datetime index, return array of strings of date
    name based on requested field (e.g. weekday_name)
    """
    cdef:
        Py_ssize_t i, count = 0
        ndarray[object] out
        pandas_datetimestruct dts
        int dow

    _dayname = np.array(
        ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'],
        dtype=np.object_)

    count = len(dtindex)
    out = np.empty(count, dtype=object)

    if field == 'weekday_name':
        for i in range(count):
            if dtindex[i] == NPY_NAT:
                out[i] = np.nan
                continue

            dt64_to_dtstruct(dtindex[i], &dts)
            dow = dayofweek(dts.year, dts.month, dts.day)
            out[i] = _dayname[dow]
        return out

    raise ValueError("Field %s not supported" % field)


@cython.wraparound(False)
def get_start_end_field(ndarray[int64_t] dtindex, object field,
                        object freqstr=None, int month_kw=12):
    """
    Given an int64-based datetime index return array of indicators
    of whether timestamps are at the start/end of the month/quarter/year
    (defined by frequency).
    """
    cdef:
        Py_ssize_t i
        int count = 0
        bint is_business = 0
        int end_month = 12
        int start_month = 1
        ndarray[int8_t] out
        ndarray[int32_t, ndim=2] _month_offset
        bint isleap
        pandas_datetimestruct dts
        int mo_off, dom, doy, dow, ldom

    _month_offset = np.array(
        [[ 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365 ],
         [ 0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366 ]],
        dtype=np.int32)

    count = len(dtindex)
    out = np.zeros(count, dtype='int8')

    if freqstr:
        if freqstr == 'C':
            raise ValueError(
                "Custom business days is not supported by %s" % field)
        is_business = freqstr[0] == 'B'

        # YearBegin(), BYearBegin() use month = starting month of year.
        # QuarterBegin(), BQuarterBegin() use startingMonth = starting
        # month of year. Other offests use month, startingMonth as ending
        # month of year.

        if (freqstr[0:2] in ['MS', 'QS', 'AS']) or (
                freqstr[1:3] in ['MS', 'QS', 'AS']):
            end_month = 12 if month_kw == 1 else month_kw - 1
            start_month = month_kw
        else:
            end_month = month_kw
            start_month = (end_month % 12) + 1
    else:
        end_month = 12
        start_month = 1

    if field == 'is_month_start':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day
                dow = dayofweek(dts.year, dts.month, dts.day)

                if (dom == 1 and dow < 5) or (dom <= 3 and dow == 0):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day

                if dom == 1:
                    out[i] = 1
            return out.view(bool)

    elif field == 'is_month_end':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                mo_off = _month_offset[isleap, dts.month - 1]
                dom = dts.day
                doy = mo_off + dom
                ldom = _month_offset[isleap, dts.month]
                dow = dayofweek(dts.year, dts.month, dts.day)

                if (ldom == doy and dow < 5) or (
                        dow == 4 and (ldom - doy <= 2)):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                mo_off = _month_offset[isleap, dts.month - 1]
                dom = dts.day
                doy = mo_off + dom
                ldom = _month_offset[isleap, dts.month]

                if ldom == doy:
                    out[i] = 1
            return out.view(bool)

    elif field == 'is_quarter_start':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day
                dow = dayofweek(dts.year, dts.month, dts.day)

                if ((dts.month - start_month) % 3 == 0) and (
                        (dom == 1 and dow < 5) or (dom <= 3 and dow == 0)):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day

                if ((dts.month - start_month) % 3 == 0) and dom == 1:
                    out[i] = 1
            return out.view(bool)

    elif field == 'is_quarter_end':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                mo_off = _month_offset[isleap, dts.month - 1]
                dom = dts.day
                doy = mo_off + dom
                ldom = _month_offset[isleap, dts.month]
                dow = dayofweek(dts.year, dts.month, dts.day)

                if ((dts.month - end_month) % 3 == 0) and (
                        (ldom == doy and dow < 5) or (
                            dow == 4 and (ldom - doy <= 2))):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                mo_off = _month_offset[isleap, dts.month - 1]
                dom = dts.day
                doy = mo_off + dom
                ldom = _month_offset[isleap, dts.month]

                if ((dts.month - end_month) % 3 == 0) and (ldom == doy):
                    out[i] = 1
            return out.view(bool)

    elif field == 'is_year_start':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day
                dow = dayofweek(dts.year, dts.month, dts.day)

                if (dts.month == start_month) and (
                        (dom == 1 and dow < 5) or (dom <= 3 and dow == 0)):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                dom = dts.day

                if (dts.month == start_month) and dom == 1:
                    out[i] = 1
            return out.view(bool)

    elif field == 'is_year_end':
        if is_business:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                dom = dts.day
                mo_off = _month_offset[isleap, dts.month - 1]
                doy = mo_off + dom
                dow = dayofweek(dts.year, dts.month, dts.day)
                ldom = _month_offset[isleap, dts.month]

                if (dts.month == end_month) and (
                        (ldom == doy and dow < 5) or (
                            dow == 4 and (ldom - doy <= 2))):
                    out[i] = 1
            return out.view(bool)
        else:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = 0
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                mo_off = _month_offset[isleap, dts.month - 1]
                dom = dts.day
                doy = mo_off + dom
                ldom = _month_offset[isleap, dts.month]

                if (dts.month == end_month) and (ldom == doy):
                    out[i] = 1
            return out.view(bool)

    raise ValueError("Field %s not supported" % field)


@cython.wraparound(False)
@cython.boundscheck(False)
def get_date_field(ndarray[int64_t] dtindex, object field):
    """
    Given a int64-based datetime index, extract the year, month, etc.,
    field and return an array of these values.
    """
    cdef:
        Py_ssize_t i, count = 0
        ndarray[int32_t] out
        ndarray[int32_t, ndim=2] _month_offset
        int isleap, isleap_prev
        pandas_datetimestruct dts
        int mo_off, doy, dow, woy

    _month_offset = np.array(
        [[ 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365 ],
         [ 0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366 ]],
        dtype=np.int32 )

    count = len(dtindex)
    out = np.empty(count, dtype='i4')

    if field == 'Y':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.year
        return out

    elif field == 'M':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.month
        return out

    elif field == 'D':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.day
        return out

    elif field == 'h':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.hour
        return out

    elif field == 'm':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.min
        return out

    elif field == 's':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.sec
        return out

    elif field == 'us':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.us
        return out

    elif field == 'ns':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.ps / 1000
        return out
    elif field == 'doy':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                out[i] = _month_offset[isleap, dts.month -1] + dts.day
        return out

    elif field == 'dow':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dayofweek(dts.year, dts.month, dts.day)
        return out

    elif field == 'woy':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                isleap = is_leapyear(dts.year)
                isleap_prev = is_leapyear(dts.year - 1)
                mo_off = _month_offset[isleap, dts.month - 1]
                doy = mo_off + dts.day
                dow = dayofweek(dts.year, dts.month, dts.day)

                # estimate
                woy = (doy - 1) - dow + 3
                if woy >= 0:
                    woy = woy / 7 + 1

                # verify
                if woy < 0:
                    if (woy > -2) or (woy == -2 and isleap_prev):
                        woy = 53
                    else:
                        woy = 52
                elif woy == 53:
                    if 31 - dts.day + dow < 3:
                        woy = 1

                out[i] = woy
        return out

    elif field == 'q':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = dts.month
                out[i] = ((out[i] - 1) / 3) + 1
        return out

    elif field == 'dim':
        with nogil:
            for i in range(count):
                if dtindex[i] == NPY_NAT:
                    out[i] = -1
                    continue

                dt64_to_dtstruct(dtindex[i], &dts)
                out[i] = days_in_month(dts)
        return out
    elif field == 'is_leap_year':
        return isleapyear_arr(get_date_field(dtindex, 'Y'))

    raise ValueError("Field %s not supported" % field)


cdef inline int days_in_month(pandas_datetimestruct dts) nogil:
    return days_per_month_table[is_leapyear(dts.year)][dts.month - 1]


cpdef isleapyear_arr(ndarray years):
    """vectorized version of isleapyear; NaT evaluates as False"""
    cdef:
        ndarray[int8_t] out

    out = np.zeros(len(years), dtype='int8')
    out[np.logical_or(years % 400 == 0,
                      np.logical_and(years % 4 == 0,
                                     years % 100 > 0))] = 1
    return out.view(bool)
