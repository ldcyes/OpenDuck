obj-m += microduck-audio.o
obj-m += microduck-max98357a.o
obj-m += microduck-dmic.o

.PHONY: dtb verify
# Offline DT only; kernel modules still require the actual configured target kernel.
dtb:
	cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I reference/tree/include -I reference/tree/arch/arm64/boot/dts/rockchip rk3576-microduck-r8.dts > rk3576-microduck-r8.preprocessed.dts
	dtc -@ -I dts -O dtb -o rk3576-microduck-r8.dtb rk3576-microduck-r8.preprocessed.dts
verify:
	python3 -B verify_artifacts.py
