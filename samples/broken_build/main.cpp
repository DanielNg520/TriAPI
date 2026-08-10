#include <iostream>
#include <vector>
#include <memory>

class Widget {
public:
    Widget(int id) : id_(id) {}
    int getId() const { return id_; }
private:
    int id_;
};

int main() {
    std::vector<std::unique_ptr<Widget>> widgets;
    widgets.push_back(std::make_unique<Widget>(1));
    widgets.push_back(std::make_unique<Widget>(2));

    std::vector<std::unique_ptr<Widget>> copy;
    for (const auto& w : widgets) {
        copy.push_back(std::make_unique<Widget>(w->getId()));
    }

    for (const auto& w : copy) {
        std::cout << "Widget ID: " << w->getId() << std::endl;
    }
    return 0;
}
