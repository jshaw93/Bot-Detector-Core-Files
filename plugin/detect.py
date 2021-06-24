from datetime import datetime, timedelta
import time

import Config
import pandas as pd
import SQL
from flask import Blueprint, request
from flask.json import jsonify

detect = Blueprint('detect', __name__, template_folder='templates')

def custom_hiscore(detection):
    # input validation
    bad_name = False
    detection['reporter'], bad_name = SQL.name_check(detection['reporter'])
    detection['reported'], bad_name = SQL.name_check(detection['reported'])

    if bad_name:
        Config.debug(f"bad name: reporter: {detection['reporter']} reported: {detection['reported']}")
        return 0

    if  not (0 <= int(detection['region_id']) <= 15522):
        return 0

    if  not (0 <= int(detection['region_id']) <= 15522):
        return 0

    # get reporter & reported
    reporter = SQL.get_player(detection['reporter'])
    reported = SQL.get_player(detection['reported'])

    create = 0
    # if reporter or reported is None (=player does not exist), create player
    if reporter is None:
        reporter = SQL.insert_player(detection['reporter'])
        create += 1

    if reported is None:
        reported = SQL.insert_player(detection['reported'])
        create += 1


    # change in detection
    detection['reported'] = int(reported.id)
    detection['reporter'] = int(reporter.id)

    # insert into reports
    SQL.insert_report(detection)
    return create


def insync_detect(detections, manual_detect):
    print("NSYNC")
    total_creates = 0
    for idx, detection in enumerate(detections):
        detection['manual_detect'] = manual_detect

        total_creates += custom_hiscore(detection)

        if len(detection) > 1000 and total_creates/len(detections) > .75:
            print(f'    Malicious: sender: {detection["reporter"]}')
            Config.debug(f'    Malicious: sender: {detection["reporter"]}')

            break

        if idx % 500 == 0 and idx != 0:
            Config.debug(f'      Completed {idx + 1}/{len(detections)}')

    Config.debug(f'      Done: Completed {idx + 1} detections')


@detect.route('/plugin/detect/<manual_detect>', methods=['POST'])
@detect.route('/<version>/plugin/detect/<manual_detect>', methods=['POST'])
def post_detect(version=None, manual_detect=0):
    detections = request.get_json()
    
    manual_detect = 0 if int(manual_detect) == 0 else 1

    df = pd.DataFrame(detections)

    #remove blank rows
    df.dropna(how="all")

    # remove duplicates
    df.drop_duplicates(subset=["reporter","reported","region_id"], inplace=True)

    #normalize time values
    df["ts"] = pd.to_datetime(df["ts"], unit='s')

    #remove any row with timestamps now within the LAST 24 hours. No future or really old entries.
    now = datetime.now()
    yesterday = datetime.now() - timedelta(days=1)
    df["ts"] = df.loc[(df["ts"] >= yesterday) & (df["ts"] <= now)]

    if len(df) > 5000 or df["reporter"].nunique() > 1:
        print('too many reports')
        Config.debug('too many reports')

        return jsonify({'NOK': 'NOK'}), 400
    
    detections = df.to_dict('records')

    print(f'      Received detections: DF shape: {df.shape}')

    Config.debug(f'      Received detections: DF shape: {df.shape}')
    Config.sched.add_job(insync_detect ,args=[detections, manual_detect], replace_existing=False, name='detect')


    return jsonify({'OK': 'OK'})
