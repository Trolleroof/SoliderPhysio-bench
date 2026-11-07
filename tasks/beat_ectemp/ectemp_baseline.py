"""Transparent ECTemp-style reference, not a validated published ECTemp replica."""

def predict(request):
    estimate = 37.0
    previous = estimate
    for row in request['history']:
        previous = estimate
        hr = row['hr'] if row['hr'] is not None else 80
        skin = row['skin_temp'] if row['skin_temp'] is not None else 34
        watts = row['watts'] if row['watts'] is not None else 0
        target = 36.7 + .012 * (hr - 70) + .045 * (skin - 33) + .001 * watts
        estimate += .08 * (target - estimate)
    if request['task'] == '3A':
        estimate += 15 * max(-.03, min(.03, estimate - previous))
    return {'mean': estimate, 'lower': estimate - .5, 'upper': estimate + .5}
