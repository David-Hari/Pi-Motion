import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class FrameStats:
	VERSION = 2

	timestamp: int   # Microseconds since UNIX epoch, UTC
	max_motion: int
	motion_sum: int
	sad_sum: int

	@classmethod
	def from_stream(cls, s):
		data = s.read(20)
		if not data:
			return None
		ft, mm, ms, ss = struct.unpack('<QIII', data)
		return cls(ft, mm, ms, ss)

	def to_stream(self, s):
		s.write(struct.pack('<QIII', self.timestamp, self.max_motion, self.motion_sum, self.sad_sum))


@dataclass
class CaptureInfo:
	name: str
	start_time: int   # Microseconds since UNIX epoch, UTC
	length_seconds: float
	max_motion: int
	max_sad: int

	@classmethod
	def from_json(cls, s: str):
		return cls(**json.loads(s))

	def to_json(self) -> str:
		return json.dumps(asdict(self))

	@classmethod
	def read_from_file(cls, file_path: Path):
		return cls.from_json(file_path.read_text()) if file_path.exists() else None

	def write_to_file(self, output_dir: Path):
		json_path = output_dir.joinpath(f'{self.name}.json')
		json_path.write_text(self.to_json(), encoding='utf_8')




def write_frame_stats(output_dir: Path, name: str, motion_stats: list[FrameStats]):
	file_path = output_dir.joinpath(f'{name}.bin')
	with open(file_path, 'wb') as f:
		f.write(struct.pack('<II', FrameStats.VERSION, len(motion_stats)))
		for stat in motion_stats:
			stat.to_stream(f)


def read_frame_stats(file_path: Path) -> list[FrameStats]:
	items = []
	with open(file_path, 'rb') as f:
		version, count = struct.unpack('<II', f.read(8))
		if version != FrameStats.VERSION:
			print(f'Unexpected version of binary file. Expected {FrameStats.VERSION}, got {version}')
			return items
		for _ in range(count):
			fs = FrameStats.from_stream(f)
			if fs is None:
				print(f'Unexpected end of file when reading motion data from {file_path.absolute()}')
				break
			items.append(fs)
	return items