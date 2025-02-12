"""Module to extract game information from SGF files."""

import os
import pathlib
import re
from typing import Any, Dict, Sequence, Union, Optional
from itertools import chain
import multiprocessing
import warnings
import functools

DEFAULT_ADVERSARY_SUBSTRINGS = ["adv"]
DEFAULT_VICTIM_SUBSTRINGS = ["victim", "bot"]


def get_game_str(path: pathlib.Path, line_num: int):
    """Return the string at a given path and line number."""
    with open(path, "r") as f:
        for i, line in enumerate(f):
            if i + 1 == line_num:
                return line


def minimize_game_str(game_str: str) -> str:
    """Strips all substrings of the form 'C[...]' from `game_str`."""
    return re.sub(r"C\[.*?\]", "", game_str)


def get_viz_link(
    path: pathlib.Path,
    line_num: int,
    minimize: bool = True,
):
    """Return a visualization link for a given path and line number."""
    game_str = get_game_str(path, line_num)
    assert game_str is not None, f"Could not find game at {path}:{line_num}"
    if minimize:
        game_str = minimize_game_str(game_str)
    return f"https://humancompatibleai.github.io/sgf-viewer/#sgf={game_str}"


def find_sgf_files(
    root: pathlib.Path, max_scan_length: int = 10000
) -> Sequence[pathlib.Path]:
    """Finds all SGF files in `root` (recursively).

    Args:
        root: The root directory to search.
        max_scan_length: The maximum number of directories to search.

    Returns:
        List of sgf paths.
    """
    sgf_paths = []
    directories_scanned = 0
    for dirpath, _, filenames in os.walk(root):
        sgf_filenames = [
            x for x in filenames if x.endswith(".sgfs") or x.endswith(".sgf")
        ]
        sgf_paths += [pathlib.Path(dirpath) / x for x in sgf_filenames]
        directories_scanned += 1
        if directories_scanned >= max_scan_length:
            warnings.warn(
                f"Reached max_scan_length, {max_scan_length}, while \
                scanning subdirectories in {root}. SGF files already found \
                will be returned."
            )
            break
    return sgf_paths


def read_and_parse_file(
    path: pathlib.Path,
    fast_parse: bool = False,
    victim_color: Optional[str] = None,
    no_victim_okay: bool = False,
    adversary_substrings: Optional[Sequence[str]] = None,
    victim_substrings: Optional[Sequence[str]] = None,
) -> Sequence[Dict[str, Any]]:
    """Parse all lines of an sgf file to a list of dictionaries with game info."""
    if adversary_substrings is None:
        adversary_substrings = DEFAULT_ADVERSARY_SUBSTRINGS
    if victim_substrings is None:
        victim_substrings = DEFAULT_VICTIM_SUBSTRINGS

    parsed_games = []
    with open(path, "r") as f:
        for i, line in enumerate(f):
            parsed_games.append(
                parse_game_str_to_dict(
                    str(path),
                    i + 1,
                    line.strip(),
                    fast_parse=fast_parse,
                    victim_color=victim_color,
                    no_victim_okay=no_victim_okay,
                    adversary_substrings=adversary_substrings,
                    victim_substrings=victim_substrings,
                )
            )
    return parsed_games


def read_and_parse_all_files(
    paths: Sequence[pathlib.Path],
    fast_parse: bool = False,
    processes: Optional[int] = 128,
    no_victim_okay: bool = False,
    adversary_substrings: Optional[Sequence[str]] = None,
    victim_substrings: Optional[Sequence[str]] = None,
) -> Sequence[Dict[str, Any]]:
    """Returns concatenated contents of all files in `paths`."""
    if adversary_substrings is None:
        adversary_substrings = DEFAULT_ADVERSARY_SUBSTRINGS
    if victim_substrings is None:
        victim_substrings = DEFAULT_VICTIM_SUBSTRINGS

    if not processes:
        processes = min(128, len(paths) // 2)
    read_and_parse_file_partial = functools.partial(
        read_and_parse_file,
        fast_parse=fast_parse,
        no_victim_okay=no_victim_okay,
        adversary_substrings=adversary_substrings,
        victim_substrings=victim_substrings,
    )
    with multiprocessing.Pool(processes=max(processes, 1)) as pool:
        parsed_games = pool.map(read_and_parse_file_partial, paths)
    return list(chain.from_iterable(parsed_games))


def extract_re(pattern: str, subject: Union[str, int]) -> Union[str, int, None]:
    """Extract first group matching `pattern` from `subject`."""
    match = re.search(pattern, str(subject))
    if match is not None:
        match_str = match.group(1)
        return int(match_str) if match_str.isdecimal() else match_str
    return None


def extract_prop(property_name: str, sgf_str: Union[str, int]) -> Union[str, int, None]:
    return extract_re(f"{property_name}\\[([^]]+)", sgf_str)


def extract_param(
    property_name: str, sgf_str: Union[str, int]
) -> Union[str, int, None]:
    return extract_re(f"{property_name}=([^,\\]]+)", sgf_str)


num_b_pass_pattern = re.compile("B\\[]")
num_w_pass_pattern = re.compile("W\\[]")
semicolon_pattern = re.compile(";")


def parse_game_str_to_dict(
    path: str,
    line_number: int,
    sgf_str: str,
    fast_parse: bool = False,
    victim_color: Optional[str] = None,
    no_victim_okay: bool = False,
    adversary_substrings: Optional[Sequence[str]] = None,
    victim_substrings: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Parse an sgf string to a dictionary containing game_info.

    Args:
        path: Path where this string was read from. We want to keep this
            information so that we can later retrieve the original string.
        line_number: Line number in the above path.
        sgf_str: The string to parse.
        fast_parse: Include additional fields that are slower to extract
            or generally less useful.
        victim_color: Which color is the victim (for SGFs whose PB and PW fields
            don't label the adversary or victim).
        no_victim_okay: If True, don't raise an error if the game doesn't have
            a victim.
        adversary_substrings: Substrings that indicate the adversary in PB or
            PW.
        victim_substrings: Substrings that indicate the victim in PB or PW.

    Returns:
        Dictionary containing game_info.
    """
    if adversary_substrings is None:
        adversary_substrings = DEFAULT_ADVERSARY_SUBSTRINGS
    if victim_substrings is None:
        victim_substrings = DEFAULT_VICTIM_SUBSTRINGS

    rule_str = extract_prop("RU", sgf_str)
    comment_str = extract_prop("C", sgf_str)
    board_size = extract_prop("SZ", sgf_str)
    whb = "0"
    if rule_str and "whb" in rule_str:
        whb = extract_re(r"whb([A-Z0-9\-]+)", rule_str)
    b_name = extract_prop("PB", sgf_str)
    w_name = extract_prop("PW", sgf_str)
    result = extract_prop("RE", sgf_str)
    komi = extract_prop("KM", sgf_str)
    komi = float(komi) if komi else komi
    win_color = result[0].lower() if result else None
    is_resignation = False
    win_score = None
    if win_color is not None:
        win_score_str = (
            result.split("+")[-1]
            if "+" in result
            # Sgfs for manual games can have a space instead of a +
            else result.split(" ")[-1]
        )
        if win_score_str == "R" or win_score_str == "Resign":
            win_score = None
            is_resignation = True
        else:
            win_score = float(win_score_str)

    b_meta = extract_prop("BR", sgf_str)
    w_meta = extract_prop("WR", sgf_str)
    b_visits = (
        extract_re(r"v([0-9]+)", b_meta) or extract_re(r"v=([0-9]+)", b_meta) or "-1"
        if b_meta
        else None
    )
    w_visits = (
        extract_re(r"v([0-9]+)", w_meta) or extract_re(r"v=([0-9]+)", w_meta) or "-1"
        if w_meta
        else None
    )

    parts = pathlib.Path(path).parts
    training = None
    if "eval" in parts:
        training = "eval"
    elif "selfplay" in parts:
        training = "train"
    elif "gatekeepersgf" in parts:
        training = "gating"

    if victim_color is None:
        b_name_has_victim = any(x in b_name.lower() for x in victim_substrings)
        w_name_has_victim = any(x in w_name.lower() for x in victim_substrings)
        b_name_has_adversary = any(x in b_name.lower() for x in adversary_substrings)
        w_name_has_adversary = any(x in w_name.lower() for x in adversary_substrings)
        victim_is_black = b_name_has_victim or w_name_has_adversary
        victim_is_white = w_name_has_victim or b_name_has_adversary
        if victim_is_black != victim_is_white:
            victim_color = "b" if victim_is_black else "w"
    assert (
        no_victim_okay or victim_color is not None
    ), f"Game doesn't have victim: path={path}, line_number={line_number}"

    victim_name = None
    victim_steps = None
    victim_rank = None
    victim_visits = None
    adv_color = None
    adv_name = None
    adv_steps = None
    adv_rank = None
    adv_visits = None
    adv_komi = None
    adv_samples = None
    adv_minus_victim_score = None
    adv_minus_victim_score_wo_komi = None
    if victim_color is not None:
        victim_name = {"b": b_name, "w": w_name}[victim_color]
        adv_color = {"b": "w", "w": "b"}[victim_color]
        adv_name = {"b": b_name, "w": w_name}[adv_color]
        if victim_name in ["bot-cp127-v1", "bot-cp505-v2", "bot-cp505-v1"]:
            victim_steps = {
                "bot-cp127-v1": 5303129600,
                "bot-cp505-v2": 11840935168,
                "bot-cp505-v1": 11840935168,
            }[victim_name]
        else:
            victim_steps = (
                # Extract step count after "-s" in the name, allowing step count to end
                # with "m" (for millions). After "-s<number>" we expect "-" or "."
                # (for names like t0-s0-d0 and victim-s1m.bin.gz) or the end of the
                # string.
                extract_re("-s(\d+m?)(?:[-.]|$)", victim_name)
                or extract_re("kata[^_]+?\-s([0-9]+)\-", "/".join(parts[-3:]))
                or 0
            )
        adv_rank = (
            extract_prop("BR", sgf_str)
            if adv_color == "b"
            else extract_prop("WR", sgf_str)
        )
        victim_rank = (
            extract_prop("BR", sgf_str)
            if adv_color == "w"
            else extract_prop("WR", sgf_str)
        )
        victim_visits = {"b": b_visits, "w": w_visits}[victim_color]
        adv_visits = {"b": b_visits, "w": w_visits}[adv_color]
        adv_komi = None if adv_color is None else komi * {"w": 1, "b": -1}[adv_color]
        adv_steps = (
            extract_re(r"\-s([0-9]+)\-", adv_name)
            or extract_re(r"t0\-s([0-9]+)\-", "/".join(parts[-3:]))
            or 0
        )
        adv_samples = extract_re(r"\-d([0-9]+)", adv_name) or 0
        if win_score is not None:
            adv_minus_victim_score = win_score if adv_color == win_color else -win_score
            adv_minus_victim_score_wo_komi = adv_minus_victim_score - adv_komi

    parsed_info = {
        "b_name": b_name,
        "w_name": w_name,
        "b_visits": b_visits,
        "w_visits": w_visits,
        # Victim info
        "victim_color": victim_color,
        "victim_name": victim_name,
        "victim_visits": (
            victim_visits
            if victim_visits
            else int(str(victim_rank).lstrip("v"))
            if victim_rank
            else 1
        ),
        "victim_steps": victim_steps,
        "victim_rsym": extract_param("rsym", victim_rank),
        "victim_algo": extract_param("algo", victim_rank),
        # Adversary info
        "adv_color": adv_color,
        "adv_name": adv_name,
        "adv_visits": adv_visits,
        "adv_steps": adv_steps,
        "adv_samples": adv_samples,
        "adv_rsym": extract_param("rsym", adv_rank),
        "adv_algo": extract_param("algo", adv_rank),
        # Scoring info
        "win_color": win_color,
        "win_name": b_name if win_color == "b" else w_name,
        "lose_name": w_name if win_color == "b" else b_name,
        "adv_win": adv_color == win_color,
        "komi": komi,
        "adv_komi": adv_komi,
        "adv_minus_victim_score": adv_minus_victim_score,
        "adv_minus_victim_score_wo_komi": adv_minus_victim_score_wo_komi,
        # Other info
        "train_status": training,
        "board_size": board_size,
        "start_turn_idx": extract_param("startTurnIdx", comment_str),
        "handicap": extract_prop("HA", sgf_str),
        "num_moves": len(semicolon_pattern.findall(sgf_str)) - 1,
        "ko_rule": extract_re(r"ko([A-Z]+)", rule_str),
        "score_rule": extract_re(r"score([A-Z]+)", rule_str),
        "tax_rule": extract_re(r"tax([A-Z]+)", rule_str),
        "sui_legal": extract_re(r"sui([0-9])", rule_str) == 1,
        "has_button": "button1" in rule_str if rule_str else False,
        "whb": whb,
        "fpok": "fpok" in rule_str if rule_str else False,
        "init_turn_num": extract_param("initTurnNum", comment_str),
        "used_initial_position": extract_param("usedInitialPosition", comment_str) == 1,
        "gtype": extract_param("gtype", comment_str),
        "is_continuation": False,
        "is_resignation": is_resignation,
        # Parsing metadata
        "sgf_path": path,
        "sgf_line": line_number,
    }

    if not fast_parse:
        # findall() is much slower than extracting a single regex
        num_b_pass = (
            len(num_b_pass_pattern.findall(sgf_str))
            + (
                len(re.findall("B\\[tt]", sgf_str))
                if isinstance(board_size, int) and board_size <= 19
                else 0
            ),
        )
        num_w_pass = (
            len(num_w_pass_pattern.findall(sgf_str))
            + (
                len(re.findall("W\\[tt]", sgf_str))
                if isinstance(board_size, int) and board_size <= 19
                else 0
            ),
        )
        parsed_info["num_b_pass"] = num_b_pass
        parsed_info["num_w_pass"] = num_w_pass
        parsed_info["num_adv_pass"] = num_b_pass if adv_color == "b" else num_w_pass
        parsed_info["num_victim_pass"] = num_w_pass if adv_color == "b" else num_b_pass

    return parsed_info
