"""The CLI's stage order is derived from dvc.yaml and respects every declared dependency."""

import pytest

from district_evolution import cli


@pytest.fixture(scope="module")
def stages():
    return cli.load_stages()


def test_every_stage_runs_after_the_stages_it_reads(stages):
    order = cli.stage_order(stages)
    assert sorted(order) == sorted(stages)
    position = {s: i for i, s in enumerate(order)}
    outs = {name: cli._paths(s.get("outs", [])) for name, s in stages.items()}
    for b, s in stages.items():
        for dep in cli._paths(s.get("deps", [])):
            for a, a_outs in outs.items():
                if a != b and any(cli._within(dep, o) or cli._within(o, dep) for o in a_outs):
                    assert position[a] < position[b], f"{b} reads {dep} from {a} but runs first"


def test_release_comes_last_and_warehouse_after_harmonization(stages):
    order = cli.stage_order(stages)
    assert order[-1] == "r01_release"
    assert order.index("h05_validate") < order.index("s11_warehouse") < order.index("s12_validate")


def test_selection(stages):
    order = cli.stage_order(stages)
    assert cli.select(order, "s11_warehouse", "s12_validate", None) == ["s11_warehouse", "s12_validate"]
    assert cli.select(order, None, None, ["r01_release", "s01_bronze_to_silver"]) == ["s01_bronze_to_silver", "r01_release"]
    with pytest.raises(SystemExit):
        cli.select(order, "no_such_stage", None, None)


def test_dry_run_prints_the_plan(capsys):
    assert cli.main(["build", "--from", "s12_validate", "--dry-run"]) == 0
    assert capsys.readouterr().out.split() == ["s12_validate", "a01_external_audit", "a02_credibility_audit",
                                               "r02_data_dictionary", "r01_release"]
