import sys
import os
import tempfile
import shutil
import pytest

src_dir = os.path.join(os.path.dirname(__file__), "..")
files_dir = os.path.join(src_dir, "files")
sys.path.append(files_dir)
import incremental_upload as iu


def create_files(rtacomplete_txt, rtacomplete_xml, copycomplete_txt):
    tmp_folder = tempfile.mkdtemp()
    if rtacomplete_txt:
        with open(tmp_folder + "/RTAComplete.txt", 'w') as RTAComplete_txt:
            RTAComplete_txt.write("foo")
    if rtacomplete_xml:
        with open(tmp_folder + "/RTAComplete.xml", 'w') as RTAComplete_xml:
            RTAComplete_xml.write("bar")
    if copycomplete_txt:
        with open(tmp_folder + "/CopyComplete.txt", 'w') as CopyComplete_txt:
            CopyComplete_txt.write("foobar")
    return tmp_folder


# parametrized with ((RTAComplete.txt, RTAComplete.xml, CopyComplete.txt), result, result_novaseq)
@pytest.mark.parametrize("permutation,result,result_novaseq", [((False, False, False), False, False), ((False, False, True), False, True),
                                                               ((False, True, False), True, False), ((False, True, True), True, True),
                                                               ((True, False, False), True, False), ((True, False, True), True, True),
                                                               ((True, True, False), True, False), ((True, True, True), True, True)])
def test_termination_file_exists(permutation, result, result_novaseq):
    run_dir = create_files(*permutation)
    actual = iu.termination_file_exists(False, run_dir)
    actual_novaseq = iu.termination_file_exists(True, run_dir)
    shutil.rmtree(run_dir)  # deleting before potential assert failure
    assert actual == result
    assert actual_novaseq == result_novaseq
