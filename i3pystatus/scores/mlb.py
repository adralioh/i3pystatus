from i3pystatus.core.util import internet, require
from i3pystatus.scores import ScoresBackend

import copy
import json
import pytz
import re
import time
from datetime import datetime
from urllib.request import urlopen

LIVE_URL = 'https://www.mlb.com/gameday/{id}'
SCOREBOARD_URL = 'http://m.mlb.com/scoreboard'
API_URL = 'https://statsapi.mlb.com/api/v1/schedule?sportId=1,51&date={date:%Y-%m-%d}&gameTypes=E,S,R,A,F,D,L,W&hydrate=team(),linescore(matchup,runners),stats,game(content(media(featured,epg),summary),tickets),seriesStatus(useOverride=true)&useLatestGames=false&language=en&leagueId=103,104,420'


class MLB(ScoresBackend):
    '''
    Backend to retrieve MLB scores. For usage examples, see :py:mod:`here
    <.scores>`.

    .. rubric:: Available formatters

    * `{home_team}` — Depending on the value of the ``team_format`` option,
      will contain either the home team's name, abbreviation, or city
    * `{home_score}` — Home team's current score
    * `{home_wins}` — Home team's number of wins
    * `{home_losses}` — Home team's number of losses
    * `{home_favorite}` — Displays the value for the :py:mod:`.scores` module's
      ``favorite`` attribute, if the home team is one of the teams being
      followed. Otherwise, this formatter will be blank.
    * `{away_team}` — Depending on the value of the ``team_format`` option,
      will contain either the away team's name, abbreviation, or city
    * `{away_score}` — Away team's current score
    * `{away_wins}` — Away team's number of wins
    * `{away_losses}` — Away team's number of losses
    * `{away_favorite}` — Displays the value for the :py:mod:`.scores` module's
      ``favorite`` attribute, if the away team is one of the teams being
      followed. Otherwise, this formatter will be blank.
    * `{top_bottom}` — Displays the value of either ``inning_top`` or
      ``inning_bottom`` based on whether the game is in the top or bottom of an
      inning.
    * `{inning}` — Current inning
    * `{outs}` — Number of outs in current inning
    * `{venue}` — Name of ballpark where game is being played
    * `{start_time}` — Start time of game in system's localtime (supports
      strftime formatting, e.g. `{start_time:%I:%M %p}`)
    * `{delay}` — Reason for delay, if game is currently delayed. Otherwise,
      this formatter will be blank.
    * `{postponed}` — Reason for postponement, if game has been postponed.
      Otherwise, this formatter will be blank.
    * `{suspended}` — Reason for suspension, if game has been suspended.
      Otherwise, this formatter will be blank.
    * `{extra_innings}` — When a game lasts longer than 9 innings, this
      formatter will show that number of innings. Otherwise, it will blank.

    .. rubric:: Team abbreviations

    * **ARI** — Arizona Diamondbacks
    * **ATL** — Atlanta Braves
    * **BAL** — Baltimore Orioles
    * **BOS** — Boston Red Sox
    * **CHC** — Chicago Cubs
    * **CIN** — Cincinnati Reds
    * **CLE** — Cleveland Guardians
    * **COL** — Colorado Rockies
    * **CWS** — Chicago White Sox
    * **DET** — Detroit Tigers
    * **HOU** — Houston Astros
    * **KC** — Kansas City Royals
    * **LAA** — Los Angeles Angels of Anaheim
    * **LAD** — Los Angeles Dodgers
    * **MIA** — Miami Marlins
    * **MIL** — Milwaukee Brewers
    * **MIN** — Minnesota Twins
    * **NYY** — New York Yankees
    * **NYM** — New York Mets
    * **OAK** — Oakland Athletics
    * **PHI** — Philadelphia Phillies
    * **PIT** — Pittsburgh Pirates
    * **SD** — San Diego Padres
    * **SEA** — Seattle Mariners
    * **SF** — San Francisco Giants
    * **STL** — St. Louis Cardinals
    * **TB** — Tampa Bay Rays
    * **TEX** — Texas Rangers
    * **TOR** — Toronto Blue Jays
    * **WSH** — Washington Nationals
    '''
    interval = 300

    settings = (
        ('favorite_teams', 'List of abbreviations of favorite teams. Games '
                           'for these teams will appear first in the scroll '
                           'list. A detailed description of how games are '
                           'ordered can be found '
                           ':ref:`here <scores-game-order>`.'),
        ('all_games', 'If set to ``True``, all games will be present in '
                      'the scroll list. If set to ``False``, then only '
                      'games from **favorite_teams** will be present in '
                      'the scroll list.'),
        ('display_order', 'When **all_games** is set to ``True``, this '
                          'option will dictate the order in which games from '
                          'teams not in **favorite_teams** are displayed'),
        ('format_no_games', 'Format used when no tracked games are scheduled '
                            'for the current day (does not support formatter '
                            'placeholders)'),
        ('format', 'Format used to display game information'),
        ('status_pregame', 'Format string used for the ``{game_status}`` '
                           'formatter when the game has not started '),
        ('status_in_progress', 'Format string used for the ``{game_status}`` '
                               'formatter when the game is in progress'),
        ('status_final', 'Format string used for the ``{game_status}`` '
                         'formatter when the game has finished'),
        ('status_postponed', 'Format string used for the ``{game_status}`` '
                             'formatter when the game has been postponed'),
        ('status_suspended', 'Format string used for the ``{game_status}`` '
                             'formatter when the game has been suspended'),
        ('inning_top', 'Value for the ``{top_bottom}`` formatter when game '
                       'is in the top half of an inning'),
        ('inning_bottom', 'Value for the ``{top_bottom}`` formatter when game '
                          'is in the bottom half of an inning'),
        ('team_colors', 'Dictionary mapping team abbreviations to hex color '
                        'codes. If overridden, the passed values will be '
                        'merged with the defaults, so it is not necessary to '
                        'define all teams if specifying this value.'),
        ('team_format', 'One of ``name``, ``abbreviation``, or ``city``. If '
                        'not specified, takes the value from the ``scores`` '
                        'module.'),
        ('date', 'Date for which to display game scores, in **YYYY-MM-DD** '
                 'format. If unspecified, the current day\'s games will be '
                 'displayed starting at 10am Eastern time, with last '
                 'evening\'s scores being shown before then. This option '
                 'exists primarily for troubleshooting purposes.'),
        ('live_url', 'Alternate URL string to launch MLB Gameday. This value '
                     'should not need to be changed'),
        ('scoreboard_url', 'Link to the MLB.com scoreboard page. Like '
                           '**live_url**, this value should not need to be '
                           'changed.'),
        ('api_url', 'Alternate URL string from which to retrieve score data. '
                    'Like **live_url*** this value should not need to be '
                    'changed.'),
    )

    required = ()

    _default_colors = {
        'ARI': '#A71930',
        'ATL': '#CE1141',
        'BAL': '#DF4601',
        'BOS': '#BD3039',
        'CHC': '#004EC1',
        'CIN': '#C6011F',
        'CLE': '#E31937',
        'COL': '#5E5EB6',
        'CWS': '#DADADA',
        'DET': '#FF6600',
        'HOU': '#EB6E1F',
        'KC': '#0046DD',
        'LAA': '#BA0021',
        'LAD': '#005A9C',
        'MIA': '#00A3E0',
        'MIL': '#0747CC',
        'MIN': '#D31145',
        'NYY': '#0747CC',
        'NYM': '#FF5910',
        'OAK': '#006659',
        'PHI': '#E81828',
        'PIT': '#FFCC01',
        'SD': '#FFC425',
        'SEA': '#2E8B90',
        'SF': '#FD5A1E',
        'STL': '#B53B30',
        'TB': '#8FBCE6',
        'TEX': '#C0111F',
        'TOR': '#0046DD',
        'WSH': '#C70003',
    }

    _valid_teams = [x for x in _default_colors]
    _valid_display_order = ['in_progress', 'suspended', 'final', 'pregame', 'postponed']

    display_order = _valid_display_order
    format_no_games = 'MLB: No games'
    format = '[{scroll} ]MLB: [{away_favorite} ]{away_team} [{away_score} ]({away_wins}-{away_losses}) at [{home_favorite} ]{home_team} [{home_score} ]({home_wins}-{home_losses}) {game_status}'
    status_pregame = '{start_time:%H:%M %Z}[ ({delay} Delay)]'
    status_in_progress = '({top_bottom} {inning}, {outs} Out)[ ({delay} Delay)]'
    status_final = '(Final[/{extra_innings}])'
    status_postponed = '(PPD: {postponed})'
    status_suspended = '(Suspended: {suspended})'
    inning_top = 'Top'
    inning_bottom = 'Bot'
    team_colors = _default_colors
    live_url = LIVE_URL
    scoreboard_url = SCOREBOARD_URL
    api_url = API_URL

    # These will inherit from the Scores class if not overridden
    team_format = None

    @require(internet)
    def check_scores(self):
        self.get_api_date()
        url = self.api_url.format(date=self.date)

        game_list = self.get_nested(
            self.api_request(url),
            'dates:0:games',
            default=[])
        if not isinstance(game_list, list):
            # When only one game is taking place during a given day, the game
            # data is just a single dict containing that game's data, rather
            # than a list of dicts. Encapsulate the single game dict in a list
            # to make it process correctly in the loop below.
            game_list = [game_list]

        # Convert list of games to dictionary for easy reference later on
        data = {}
        team_game_map = {}
        for game in game_list:
            try:
                id_ = game['gamePk']
            except (KeyError, TypeError):
                continue

            away_abbrev = self.get_nested(
                game,
                'teams:away:team:abbreviation').upper()
            home_abbrev = self.get_nested(
                game,
                'teams:home:team:abbreviation').upper()
            if away_abbrev and home_abbrev:
                try:
                    for team in (home_abbrev, away_abbrev):
                        if team in self.favorite_teams:
                            team_game_map.setdefault(team, []).append(id_)
                except KeyError:
                    continue

            data[id_] = game

        self.interpret_api_return(data, team_game_map)

    def process_game(self, game):
        ret = {}

        self.logger.debug(f'Processing {self.name} game data: {game}')

        linescore = self.get_nested(game, 'linescore', default={})

        ret['id'] = game['gamePk']
        ret['inning'] = self.get_nested(linescore, 'currentInning', default=0)
        ret['outs'] = self.get_nested(linescore, 'outs')
        ret['live_url'] = self.live_url.format(id=ret['id'])

        for team in ('away', 'home'):
            team_data = self.get_nested(game, f'teams:{team}', default={})

            if team == 'home':
                ret['venue'] = self.get_nested(team_data, 'venue:name')

            ret[f'{team}_city'] = self.get_nested(
                team_data,
                'team:locationName')
            ret[f'{team}_name'] = self.get_nested(
                team_data,
                'team:teamName')
            ret[f'{team}_abbreviation'] = self.get_nested(
                team_data,
                'team:abbreviation')

            ret[f'{team}_wins'] = self.get_nested(
                team_data,
                'leagueRecord:wins',
                callback=self.zero_fallback,
                default=0)
            ret[f'{team}_losses'] = self.get_nested(
                team_data,
                'leagueRecord:losses',
                callback=self.zero_fallback,
                default=0)

            ret[f'{team}_score'] = self.get_nested(
                linescore,
                f'teams:{team}:runs',
                callback=self.zero_fallback,
                default=0)

        for key in ('delay', 'postponed', 'suspended'):
            ret[key] = ''

        ret['status'] = self.get_nested(game, 'status:detailedState').replace(' ', '_').lower()

        if ret['status'] == 'delayed_start':
            ret['status'] = 'pregame'
            ret['delay'] = self.get_nested(game, 'status:reason', default='Unknown')
        elif ret['status'].startswith('delayed'):
            ret['status'] = 'in_progress'
            ret['delay'] = game['status']['detailedState'].split(':', 1)[-1].strip()
        elif ret['status'] == 'postponed':
            ret['postponed'] = self.get_nested(game, 'status:reason', default='Unknown Reason')
        elif ret['status'].startswith('suspended'):
            ret['status'] = 'suspended'
            ret['suspended'] = self.get_nested(
                game,
                'status:detailedState',
                default='Suspended').replace('Suspended: ', '')
        elif ret['status'].startswith('completed_early') or ret['status'] == 'game_over':
            ret['status'] = 'final'
        elif ret['status'] not in ('in_progress', 'final'):
            ret['status'] = 'pregame'

        try:
            ret['extra_innings'] = ret['inning'] \
                if ret['status'] == 'final' and ret['inning'] != 9 \
                else ''
        except ValueError:
            ret['extra_innings'] = ''

        top_bottom = self.get_nested(linescore, 'inningHalf').lower()
        ret['top_bottom'] = self.inning_top if top_bottom == 'top' \
            else self.inning_bottom if top_bottom == 'bottom' \
            else ''

        try:
            game_time = datetime.strptime(
                self.get_nested(game, 'gameDate'),
                '%Y-%m-%dT%H:%M:%SZ')
        except ValueError as exc:
            # Log when the date retrieved from the API return doesn't match the
            # expected format (to help troubleshoot API changes), and set an
            # actual datetime so format strings work as expected. The times
            # will all be wrong, but the logging here will help us make the
            # necessary changes to adapt to any API changes.
            self.logger.exception(
                f'Error encountered determining {self.name} game time for '
                f'game {game["gamePk"]}'
            )
            game_time = datetime(1970, 1, 1)

        ret['start_time'] = pytz.timezone('UTC').localize(game_time).astimezone()

        self.logger.debug(f'Returned {self.name} formatter data: {ret}')

        return ret
