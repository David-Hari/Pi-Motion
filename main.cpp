#include <iomanip>
#include <iostream>
#include <memory>
#include <thread>

#include <libcamera/libcamera.h>
#include <libcamera/base/shared_fd.h>
#include <opencv2/opencv.hpp>

using namespace libcamera;
using namespace std::chrono_literals;

static std::atomic<bool> recording{false};
static std::deque<cv::Mat> prebuffer;
static const int PREBUFFER_FRAMES = 150;	// ~10s at 15fps
static const double MOTION_THRESHOLD = 25.0;	// motion sensitivity
static const int POST_MOTION_FRAMES = 150;	// record 10s after motion stops
static const int FRAME_WIDTH = 1920, FRAME_HEIGHT = 1080, FPS = 15;

static std::shared_ptr<libcamera::Camera> camera;
static cv::VideoWriter writer;
static int postCount = 0;
static cv::Mat lastGray;


// Converts libcamera buffer to OpenCV Mat (YUV -> grayscale)
cv::Mat bufferToMat(const FrameBuffer *buffer) {
	const FrameMetadata &meta = buffer->metadata();
	if (meta.planes().empty()) {
		return {};
	}

	const auto &plane = meta.planes()[0];
	void *mem = mmap(nullptr, plane.bytesused, PROT_READ, MAP_SHARED, buffer->planes()[0].fd.get(), 0);
	if (mem == MAP_FAILED) {
		return {};
	}

	cv::Mat gray(FRAME_HEIGHT, FRAME_WIDTH, CV_8UC1, buffer->planes()[0].fd.get());
	cv::Mat copy = gray.clone(); // copy before unmap
	munmap(mem, plane.bytesused);
	return copy;
}


static void requestComplete(Request *request) {
	if (request->status() == Request::RequestCancelled) {
		return;
	}
	const FrameBuffer *buffer = request->buffers().begin()->second;
	if (buffer->metadata().planes().empty()) {
		return;
	}
	cv::Mat frame(FRAME_HEIGHT, FRAME_WIDTH, CV_8UC1, buffer->planes()[0].fd.get());
	
	if (!writer.isOpened()) {
		std::string filename = "/mnt/video/" + std::to_string(std::time(nullptr)) + ".avi";
		writer.open(filename, cv::VideoWriter::fourcc('M','J','P','G'), FPS, {FRAME_WIDTH, FRAME_HEIGHT}, true);
	}
	writer.write(frame)
	/*
	
	// motion detection
	cv::Mat diff;
	if (!lastGray.empty()) {
		cv::absdiff(frame, lastGray, diff);
		double motion = cv::mean(diff)[0];
		if (motion > MOTION_THRESHOLD) {
			if (!recording) {
				std::string filename = "/mnt/video/" + std::to_string(std::time(nullptr)) + ".avi";
				writer.open(filename, cv::VideoWriter::fourcc('M','J','P','G'), FPS, {FRAME_WIDTH, FRAME_HEIGHT}, false);
				for (auto &f : prebuffer) {
					writer.write(f);
				}
				prebuffer.clear();
				recording = true;
				postCount = POST_MOTION_FRAMES;
				std::cout << "Motion start: " << filename << "\n";
			}
			else {
				postCount = POST_MOTION_FRAMES;
			}
		}
	}
	lastGray = frame.clone();

	if (recording) {
		writer.write(frame);
		if (--postCount <= 0) {
			writer.release();
			recording = false;
			std::cout << "Motion end\n";
		}
	}
	else {
		prebuffer.push_back(frame);
		if (prebuffer.size() > PREBUFFER_FRAMES)
			prebuffer.pop_front();
	}
	*/

	request->reuse(Request::ReuseBuffers);
	camera->queueRequest(request); // Re-queue for next frame
}

int main() {
	CameraManager cm;
	cm.start();

	if (cm.cameras().empty()) {
		std::cerr << "No cameras were identified on the system" << std::endl;
		cm.stop();
		return EXIT_FAILURE;
	}

	camera = cm.get(cm.cameras()[0]->id());
	camera->acquire();

	std::unique_ptr<CameraConfiguration> config = camera->generateConfiguration({ StreamRole::VideoRecording });
	StreamConfiguration &streamConfig = config->at(0);
	streamConfig.size = { FRAME_WIDTH, FRAME_HEIGHT };
	config->validate();
	std::cout << "Validated camera configuration is: " << streamConfig.toString() << std::endl;
	camera->configure(config.get());

	FrameBufferAllocator *allocator = new FrameBufferAllocator(camera);
	for (StreamConfiguration &cfg : *config) {
		int ret = allocator->allocate(cfg.stream());
		if (ret < 0) {
			std::cerr << "Can't allocate buffers" << std::endl;
			return -ENOMEM;
		}

		size_t allocated = allocator->buffers(cfg.stream()).size();
		std::cout << "Allocated " << allocated << " buffers for stream" << std::endl;
	}
	Stream *stream = streamConfig.stream();
	
	std::vector<std::unique_ptr<Request>> requests;
	for (const std::unique_ptr<FrameBuffer> &buffer : allocator->buffers(stream)) {
		std::unique_ptr<Request> request = camera->createRequest();
		if (!request) {
			std::cerr << "Can't create request" << std::endl;
			return -ENOMEM;
		}
		int ret = request->addBuffer(stream, buffer.get());
		if (ret < 0) {
			std::cerr << "Can't set buffer for request" << std::endl;
			return ret;
		}
		requests.push_back(std::move(request));
	}

	camera->requestCompleted.connect(requestComplete);

	camera->start();
	for (auto &request : requests) {
		camera->queueRequest(request.get());
	}

	std::cout << "Running... Press Ctrl+C to stop.\n";
	while (true) {
		std::this_thread::sleep_for(std::chrono::seconds(1));
	}

	std::cout << "Stopping.\n";
	writer.release();
	camera->stop();
	allocator->free(stream);
	delete allocator;
	camera->release();
	camera.reset();
	cm.stop();

	return 0;
}
