import json, os
from datetime import datetime, timedelta, timezone
from nba_api.stats.endpoints import scoreboardv2

os.makedirs('data', exist_ok=True)

def fetch_by_date(date_str, out_path):
    try:
        sb = scoreboardv2.ScoreboardV2(game_date=date_str, league_id='00')
        data = sb.get_dict()

        game_headers = next(r for r in data['resultSets'] if r['name'] == 'GameHeader')
        line_scores  = next(r for r in data['resultSets'] if r['name'] == 'LineScore')

        gh = game_headers['headers']
        lh = line_scores['headers']

        scores = {}
        for row in line_scores['rowSet']:
            r = dict(zip(lh, row))
            gid = r['GAME_ID']
            if gid not in scores:
                scores[gid] = []
            wl = r.get('TEAM_WINS_LOSSES') or '0-0'
            wins, losses = wl.split('-') if '-' in wl else ('0', '0')
            scores[gid].append({
                'teamTricode': r['TEAM_ABBREVIATION'],
                'score': int(r['PTS'] or 0),
                'wins': int(wins),
                'losses': int(losses),
                'periods': []
            })

        games = []
        for row in game_headers['rowSet']:
            r = dict(zip(gh, row))
            gid = r['GAME_ID']
            sc = scores.get(gid, [{}, {}])
            away = sc[0] if len(sc) > 0 else {}
            home = sc[1] if len(sc) > 1 else {}
            status = int(r.get('GAME_STATUS_ID') or 1)
            games.append({
                'gameId':      gid,
                'gameStatus':  status,
                'gameTimeUTC': r.get('GAME_DATE_EST'),
                'period':      int(r.get('LIVE_PERIOD') or 0),
                'gameClock':   '',
                'awayScore':   away.get('score', 0),
                'homeScore':   home.get('score', 0),
                'awayPeriods': [],
                'homePeriods': [],
                'awayTeam':    away,
                'homeTeam':    home,
                'gameEt':      r.get('GAME_DATE_EST', ''),
            })

        result = {
            'scoreboard': {'gameDate': date_str, 'games': games},
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }
        with open(out_path, 'w') as f:
            f.write('var NBA_SCOREBOARD = ' + json.dumps(result) + ';')
        print(f"OK: {out_path} — {len(games)} games")
    except Exception as e:
        print(f"ERROR {date_str}: {e}")

# HOY via live endpoint
try:
    import urllib.request
    req = urllib.request.Request(
        'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json',
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nba.com/'}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        today_data = json.loads(r.read())
    today_data['fetched_at'] = datetime.now(timezone.utc).isoformat()
    with open('data/scoreboard-data.js', 'w') as f:
        f.write('var NBA_SCOREBOARD = ' + json.dumps(today_data) + ';')
    print("OK: today")
except Exception as e:
    print(f"Today failed: {e}")

# AYER y MAÑANA
today = datetime.now(timezone.utc).date()
fetch_by_date(str(today - timedelta(days=1)), 'data/scoreboard-yesterday.js')
fetch_by_date(str(today + timedelta(days=1)), 'data/scoreboard-tomorrow.js')

# ── STANDINGS ──
try:
    from nba_api.stats.endpoints import leaguestandingsv3
    st = leaguestandingsv3.LeagueStandingsV3(league_id='00', season_type='Regular Season')
    data = st.get_dict()
    rs = next(r for r in data['resultSets'] if r['name'] == 'Standings')
    h = rs['headers']

    east, west = [], []
    for row in rs['rowSet']:
        r = dict(zip(h, row))
        team = {
            'tricode': r['TeamAbbreviation'],
            'name':    r['TeamName'],
            'wins':    r['WINS'],
            'losses':  r['LOSSES'],
            'pct':     f"{float(r['WinPCT']):.3f}",
            'gb':      r['ConferenceGamesBack'] or '—',
        }
        if r['Conference'] == 'East':
            east.append(team)
        else:
            west.append(team)

    standings = {
        'east': sorted(east, key=lambda x: (-x['wins'], x['losses'])),
        'west': sorted(west, key=lambda x: (-x['wins'], x['losses'])),
        'updated': datetime.now(timezone.utc).isoformat()
    }
    with open('data/standings.js', 'w') as f:
        f.write('var NBA_STANDINGS = ' + json.dumps(standings) + ';')
    print(f"OK: standings — {len(east)} East, {len(west)} West")
except Exception as e:
    print(f"Standings error: {e}")
