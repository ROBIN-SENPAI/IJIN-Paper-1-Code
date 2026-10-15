@echo off
set PYTHONIOENCODING=utf-8
cd /d E:\A-PQZTO_work\code
python run_city.py main 7 > E:\A-PQZTO_work\results\city_main_log.txt 2>&1
python run_city.py trace 7 > E:\A-PQZTO_work\results\city_trace_log.txt 2>&1
python run_city.py twin 7 > E:\A-PQZTO_work\results\city_twin_log.txt 2>&1
python run_city.py scal 1 > E:\A-PQZTO_work\results\city_scal_log.txt 2>&1
python pqc_bench.py > E:\A-PQZTO_work\results\pqc_log.txt 2>&1
echo done > E:\A-PQZTO_work\results\PIPELINE_DONE.txt
