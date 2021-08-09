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
    print(tmp_folder)
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
@pytest.mark.parametrize("permutation,result,result_novaseq", [((False, False, False), True, True), ((False, False, True), True, False),
                                                               ((False, True, False), False, True), ((False, True, True), False, False), ((True, False, False), False, True),
                                                               ((True, False, True), False, False), ((True, True, False), False, True), ((True, True, True), False, False)])
def test_is_still_uploading(permutation, result, result_novaseq):
    run_dir = create_files(*permutation)
    actual = iu.is_still_uploading(False, run_dir)
    actual_novaseq = iu.is_still_uploading(True, run_dir)
    shutil.rmtree(run_dir)
    assert actual == result
    assert actual_novaseq == result_novaseq
